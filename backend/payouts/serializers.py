from rest_framework import serializers

from payouts.models import BankAccount, LedgerEntry, Merchant, Payout
from payouts.services import MerchantBalance


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = [
            "id",
            "account_holder_name",
            "account_number",
            "ifsc_code",
            "is_active",
            "created_at",
        ]


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = [
            "id",
            "entry_type",
            "amount_paise",
            "description",
            "payout_id",
            "created_at",
        ]


class PayoutSerializer(serializers.ModelSerializer):
    bank_account = BankAccountSerializer(read_only=True)

    class Meta:
        model = Payout
        fields = [
            "id",
            "amount_paise",
            "status",
            "attempt_count",
            "failure_reason",
            "bank_account",
            "processing_started_at",
            "created_at",
            "updated_at",
        ]


class PayoutCreateSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.UUIDField()


class MerchantBalanceSerializer(serializers.Serializer):
    available_balance_paise = serializers.IntegerField()
    held_balance_paise = serializers.IntegerField()


class MerchantDashboardSerializer(serializers.Serializer):
    merchant_id = serializers.UUIDField()
    merchant_name = serializers.CharField()
    balance = MerchantBalanceSerializer()
    bank_accounts = BankAccountSerializer(many=True)
    recent_ledger_entries = LedgerEntrySerializer(many=True)
    payouts = PayoutSerializer(many=True)


def build_dashboard_payload(
    *,
    merchant: Merchant,
    balance: MerchantBalance,
    bank_accounts,
    ledger_entries,
    payouts,
):
    return {
        "merchant_id": merchant.id,
        "merchant_name": merchant.name,
        "balance": {
            "available_balance_paise": balance.available_balance_paise,
            "held_balance_paise": balance.held_balance_paise,
        },
        "bank_accounts": BankAccountSerializer(bank_accounts, many=True).data,
        "recent_ledger_entries": LedgerEntrySerializer(ledger_entries, many=True).data,
        "payouts": PayoutSerializer(payouts, many=True).data,
    }
