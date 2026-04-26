from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from payouts.models import BankAccount, LedgerEntry, Merchant, Payout
from payouts.serializers import (
    BankAccountSerializer,
    LedgerEntrySerializer,
    PayoutCreateSerializer,
    PayoutSerializer,
    build_dashboard_payload,
)
from payouts.services import (
    IdempotencyConflictError,
    InsufficientBalanceError,
    InvalidBankAccountError,
    PayoutError,
    create_payout_request,
    get_merchant_balance,
)


def get_merchant_or_404(merchant_id: str) -> Merchant:
    return get_object_or_404(Merchant, id=merchant_id)


class MerchantDashboardView(APIView):
    def get(self, request, merchant_id):
        merchant = get_merchant_or_404(merchant_id)
        balance = get_merchant_balance(merchant.id)
        bank_accounts = BankAccount.objects.filter(merchant=merchant).order_by(
            "-created_at"
        )
        ledger_entries = LedgerEntry.objects.filter(merchant=merchant).order_by(
            "-created_at"
        )[:10]
        payouts = Payout.objects.filter(merchant=merchant).order_by("-created_at")[:10]

        payload = build_dashboard_payload(
            merchant=merchant,
            balance=balance,
            bank_accounts=bank_accounts,
            ledger_entries=ledger_entries,
            payouts=payouts,
        )
        return Response(payload)


class MerchantBalanceView(APIView):
    def get(self, request, merchant_id):
        merchant = get_merchant_or_404(merchant_id)
        balance = get_merchant_balance(merchant.id)
        return Response(
            {
                "merchant_id": merchant.id,
                "available_balance_paise": balance.available_balance_paise,
                "held_balance_paise": balance.held_balance_paise,
            }
        )


class MerchantLedgerView(APIView):
    def get(self, request, merchant_id):
        merchant = get_merchant_or_404(merchant_id)
        entries = LedgerEntry.objects.filter(merchant=merchant).order_by("-created_at")
        return Response(
            {
                "merchant_id": merchant.id,
                "results": LedgerEntrySerializer(entries, many=True).data,
            }
        )


class MerchantPayoutListView(APIView):
    def get(self, request, merchant_id):
        merchant = get_merchant_or_404(merchant_id)
        payouts = Payout.objects.filter(merchant=merchant).order_by("-created_at")
        return Response(
            {
                "merchant_id": merchant.id,
                "results": PayoutSerializer(payouts, many=True).data,
            }
        )


class PayoutCreateView(APIView):
    IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"
    MERCHANT_HEADER = "HTTP_X_MERCHANT_ID"

    def post(self, request):
        merchant_id = request.META.get(self.MERCHANT_HEADER)
        if not merchant_id:
            return Response(
                {"detail": "Missing X-Merchant-Id header."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        raw_idempotency_key = request.META.get(self.IDEMPOTENCY_HEADER)
        if not raw_idempotency_key:
            return Response(
                {"detail": "Missing Idempotency-Key header."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed_idempotency_key = UUID(raw_idempotency_key)
        except ValueError:
            return Response(
                {"detail": "Idempotency-Key must be a valid UUID."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        merchant = get_merchant_or_404(merchant_id)
        serializer = PayoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payout, created = create_payout_request(
                merchant_id=merchant.id,
                bank_account_id=serializer.validated_data["bank_account_id"],
                amount_paise=serializer.validated_data["amount_paise"],
                idempotency_key=parsed_idempotency_key,
            )
        except InvalidBankAccountError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InsufficientBalanceError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except IdempotencyConflictError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except PayoutError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_status = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        return Response(PayoutSerializer(payout).data, status=response_status)
