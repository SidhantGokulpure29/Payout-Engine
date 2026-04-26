from dataclasses import dataclass
from datetime import timedelta
import hashlib
import random
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import BigIntegerField, Case, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from payouts.models import BankAccount, IdempotencyKey, LedgerEntry, Merchant, Payout


class PayoutError(Exception):
    pass


class InsufficientBalanceError(PayoutError):
    pass


class IdempotencyConflictError(PayoutError):
    pass


class InvalidBankAccountError(PayoutError):
    pass


class PayoutNotProcessableError(PayoutError):
    pass


@dataclass(frozen=True)
class MerchantBalance:
    available_balance_paise: int
    held_balance_paise: int


def _sum_for_entry_type(entry_type):
    return Coalesce(
        Sum(
            Case(
                When(entry_type=entry_type, then=F("amount_paise")),
                default=Value(0),
                output_field=BigIntegerField(),
            )
        ),
        0,
    )


def get_merchant_balance(merchant_id: UUID) -> MerchantBalance:
    aggregates = LedgerEntry.objects.filter(merchant_id=merchant_id).aggregate(
        credits=_sum_for_entry_type(LedgerEntry.EntryType.CREDIT),
        holds=_sum_for_entry_type(LedgerEntry.EntryType.HOLD),
        releases=_sum_for_entry_type(LedgerEntry.EntryType.RELEASE),
        debits=_sum_for_entry_type(LedgerEntry.EntryType.DEBIT),
    )

    available_balance = (
        aggregates["credits"] + aggregates["releases"] - aggregates["holds"]
    )
    held_balance = aggregates["holds"] - aggregates["releases"] - aggregates["debits"]

    return MerchantBalance(
        available_balance_paise=available_balance,
        held_balance_paise=held_balance,
    )


def _build_request_fingerprint(amount_paise: int, bank_account_id: UUID) -> str:
    payload = f"{amount_paise}:{bank_account_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_payout_request(
    *,
    merchant_id: UUID,
    bank_account_id: UUID,
    amount_paise: int,
    idempotency_key: UUID,
) -> tuple[Payout, bool]:
    if amount_paise <= 0:
        raise PayoutError("Payout amount must be positive.")

    now = timezone.now()
    request_fingerprint = _build_request_fingerprint(amount_paise, bank_account_id)

    with transaction.atomic():
        merchant = Merchant.objects.select_for_update().get(id=merchant_id)

        IdempotencyKey.objects.filter(
            merchant=merchant,
            key=idempotency_key,
            expires_at__lte=now,
        ).delete()

        existing_record = (
            IdempotencyKey.objects.select_for_update()
            .filter(merchant=merchant, key=idempotency_key)
            .first()
        )
        if existing_record is not None:
            if existing_record.request_fingerprint != request_fingerprint:
                raise IdempotencyConflictError(
                    "This idempotency key was already used with a different request."
                )
            if existing_record.payout is None:
                raise PayoutError("Existing idempotent request is still being created.")
            return existing_record.payout, False

        bank_account = (
            BankAccount.objects.select_for_update()
            .filter(id=bank_account_id, merchant=merchant, is_active=True)
            .first()
        )
        if bank_account is None:
            raise InvalidBankAccountError(
                "Bank account does not belong to this merchant or is inactive."
            )

        balance = get_merchant_balance(merchant.id)
        if balance.available_balance_paise < amount_paise:
            raise InsufficientBalanceError("Insufficient available balance.")

        payout = Payout.objects.create(
            merchant=merchant,
            bank_account=bank_account,
            amount_paise=amount_paise,
            status=Payout.Status.PENDING,
            idempotency_key=idempotency_key,
        )
        LedgerEntry.objects.create(
            merchant=merchant,
            payout=payout,
            entry_type=LedgerEntry.EntryType.HOLD,
            amount_paise=amount_paise,
            description="Funds held for payout request.",
        )

        try:
            IdempotencyKey.objects.create(
                merchant=merchant,
                key=idempotency_key,
                payout=payout,
                request_fingerprint=request_fingerprint,
                expires_at=now
                + timedelta(seconds=settings.IDEMPOTENCY_KEY_TTL_SECONDS),
            )
        except IntegrityError as exc:
            raise PayoutError("Could not persist idempotency record.") from exc

    return payout, True


def mark_payout_processing(*, payout_id: UUID, increment_attempt: bool = True) -> Payout:
    with transaction.atomic():
        payout = (
            Payout.objects.select_for_update()
            .select_related("merchant")
            .get(id=payout_id)
        )
        if payout.status != Payout.Status.PENDING:
            raise PayoutNotProcessableError("Only pending payouts can start processing.")

        payout.transition_to(Payout.Status.PROCESSING)
        if increment_attempt:
            payout.attempt_count += 1
        payout.processing_started_at = timezone.now()
        payout.failure_reason = ""
        payout.save(
            update_fields=[
                "status",
                "attempt_count",
                "processing_started_at",
                "failure_reason",
                "updated_at",
            ]
        )
        return payout


def complete_payout(*, payout_id: UUID) -> Payout:
    with transaction.atomic():
        payout = (
            Payout.objects.select_for_update()
            .select_related("merchant")
            .get(id=payout_id)
        )
        if payout.status != Payout.Status.PROCESSING:
            raise PayoutNotProcessableError(
                "Only processing payouts can be completed."
            )

        payout.transition_to(Payout.Status.COMPLETED)
        payout.save(update_fields=["status", "updated_at"])
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            payout=payout,
            entry_type=LedgerEntry.EntryType.DEBIT,
            amount_paise=payout.amount_paise,
            description="Payout completed and funds debited.",
        )
        return payout


def fail_payout(*, payout_id: UUID, reason: str) -> Payout:
    with transaction.atomic():
        payout = (
            Payout.objects.select_for_update()
            .select_related("merchant")
            .get(id=payout_id)
        )
        if payout.status != Payout.Status.PROCESSING:
            raise PayoutNotProcessableError("Only processing payouts can fail.")

        payout.transition_to(Payout.Status.FAILED)
        payout.failure_reason = reason
        payout.save(update_fields=["status", "failure_reason", "updated_at"])
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            payout=payout,
            entry_type=LedgerEntry.EntryType.RELEASE,
            amount_paise=payout.amount_paise,
            description="Held funds released after payout failure.",
        )
        return payout


def choose_settlement_outcome() -> str:
    draw = random.random()
    if draw < 0.7:
        return "success"
    if draw < 0.9:
        return "failure"
    return "hang"


def get_stuck_payouts():
    threshold = timezone.now() - timedelta(
        seconds=settings.PAYOUT_STUCK_THRESHOLD_SECONDS
    )
    return Payout.objects.filter(
        status=Payout.Status.PROCESSING,
        processing_started_at__lte=threshold,
    ).order_by("processing_started_at")


def mark_stuck_payout_ready_for_retry(*, payout_id: UUID) -> Payout:
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        if payout.status != Payout.Status.PROCESSING:
            raise PayoutNotProcessableError(
                "Only processing payouts can be retried."
            )

        payout.processing_started_at = None
        payout.failure_reason = ""
        payout.save(
            update_fields=[
                "processing_started_at",
                "failure_reason",
                "updated_at",
            ]
        )
        return payout
