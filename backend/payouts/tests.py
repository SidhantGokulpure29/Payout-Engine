from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from django.test import TransactionTestCase

from payouts.models import BankAccount, LedgerEntry, Merchant, Payout
from payouts.services import (
    InsufficientBalanceError,
    create_payout_request,
    get_merchant_balance,
    mark_payout_processing,
    mark_stuck_payout_ready_for_retry,
    process_payout_inline,
    sweep_unprocessed_payouts,
)


class PayoutServiceTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Test Merchant",
            email="merchant@example.com",
        )
        self.bank_account = BankAccount.objects.create(
            merchant=self.merchant,
            account_number="1234567890",
            ifsc_code="HDFC0001234",
            account_holder_name="Test Merchant",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            entry_type=LedgerEntry.EntryType.CREDIT,
            amount_paise=10_000,
            description="Initial funded balance",
        )

    def test_idempotent_payout_request_returns_same_payout(self):
        idempotency_key = uuid4()

        first_payout, first_created = create_payout_request(
            merchant_id=self.merchant.id,
            bank_account_id=self.bank_account.id,
            amount_paise=2_500,
            idempotency_key=idempotency_key,
        )
        second_payout, second_created = create_payout_request(
            merchant_id=self.merchant.id,
            bank_account_id=self.bank_account.id,
            amount_paise=2_500,
            idempotency_key=idempotency_key,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_payout.id, second_payout.id)
        self.assertEqual(Payout.objects.count(), 1)
        self.assertEqual(
            LedgerEntry.objects.filter(entry_type=LedgerEntry.EntryType.HOLD).count(),
            1,
        )

    def test_concurrent_payout_requests_allow_only_one_success(self):
        def submit_payout():
            try:
                payout, _ = create_payout_request(
                    merchant_id=self.merchant.id,
                    bank_account_id=self.bank_account.id,
                    amount_paise=6_000,
                    idempotency_key=uuid4(),
                )
                return ("created", payout.id)
            except InsufficientBalanceError:
                return ("insufficient_balance", None)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit_payout(), range(2)))

        created_count = sum(1 for result, _ in results if result == "created")
        rejected_count = sum(
            1 for result, _ in results if result == "insufficient_balance"
        )

        self.assertEqual(created_count, 1)
        self.assertEqual(rejected_count, 1)
        self.assertEqual(Payout.objects.count(), 1)

        balance = get_merchant_balance(self.merchant.id)
        self.assertEqual(balance.available_balance_paise, 4_000)
        self.assertEqual(balance.held_balance_paise, 6_000)

    def test_retry_prep_does_not_consume_attempt_until_processing_restarts(self):
        payout, _ = create_payout_request(
            merchant_id=self.merchant.id,
            bank_account_id=self.bank_account.id,
            amount_paise=2_500,
            idempotency_key=uuid4(),
        )

        mark_payout_processing(payout_id=payout.id)
        payout.refresh_from_db()
        self.assertEqual(payout.attempt_count, 1)
        self.assertEqual(payout.status, Payout.Status.PROCESSING)

        mark_stuck_payout_ready_for_retry(payout_id=payout.id)
        payout.refresh_from_db()
        self.assertEqual(payout.attempt_count, 1)
        self.assertIsNone(payout.processing_started_at)
        self.assertEqual(payout.status, Payout.Status.PROCESSING)

    def test_process_payout_inline_transitions_out_of_pending(self):
        payout, _ = create_payout_request(
            merchant_id=self.merchant.id,
            bank_account_id=self.bank_account.id,
            amount_paise=2_500,
            idempotency_key=uuid4(),
        )

        process_payout_inline(payout_id=payout.id)
        payout.refresh_from_db()

        self.assertNotEqual(payout.status, Payout.Status.PENDING)
        self.assertEqual(payout.attempt_count, 1)

    def test_sweep_unprocessed_payouts_fails_exhausted_stuck_payout(self):
        payout, _ = create_payout_request(
            merchant_id=self.merchant.id,
            bank_account_id=self.bank_account.id,
            amount_paise=2_500,
            idempotency_key=uuid4(),
        )

        mark_payout_processing(payout_id=payout.id)
        payout.attempt_count = 3
        payout.save(update_fields=["attempt_count", "updated_at"])

        sweep_unprocessed_payouts()
        payout.refresh_from_db()

        self.assertEqual(payout.status, Payout.Status.FAILED)
