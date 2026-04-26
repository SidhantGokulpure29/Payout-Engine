from django.core.management.base import BaseCommand

from payouts.models import BankAccount, LedgerEntry, Merchant


class Command(BaseCommand):
    help = "Seed merchants, bank accounts, and initial credit ledger entries."

    def handle(self, *args, **options):
        merchants = [
            {
                "name": "Acme Agency",
                "email": "finance@acme.example",
                "account_holder_name": "Acme Agency LLP",
                "account_number": "100000000001",
                "ifsc_code": "HDFC0001001",
                "credits": [
                    (75_000, "Client payout from US customer"),
                    (25_000, "Top-up adjustment"),
                ],
            },
            {
                "name": "Bluebird Studio",
                "email": "hello@bluebird.example",
                "account_holder_name": "Bluebird Studio",
                "account_number": "100000000002",
                "ifsc_code": "ICIC0002002",
                "credits": [
                    (150_000, "Invoice settlement"),
                    (10_000, "Referral bonus"),
                ],
            },
            {
                "name": "Freelance Ravi",
                "email": "ravi@freelance.example",
                "account_holder_name": "Ravi Kumar",
                "account_number": "100000000003",
                "ifsc_code": "SBIN0003003",
                "credits": [
                    (50_000, "Project payment"),
                ],
            },
        ]

        for merchant_data in merchants:
            merchant, _ = Merchant.objects.get_or_create(
                email=merchant_data["email"],
                defaults={
                    "name": merchant_data["name"],
                },
            )
            BankAccount.objects.get_or_create(
                merchant=merchant,
                account_number=merchant_data["account_number"],
                defaults={
                    "ifsc_code": merchant_data["ifsc_code"],
                    "account_holder_name": merchant_data["account_holder_name"],
                    "is_active": True,
                },
            )

            for amount_paise, description in merchant_data["credits"]:
                LedgerEntry.objects.get_or_create(
                    merchant=merchant,
                    entry_type=LedgerEntry.EntryType.CREDIT,
                    amount_paise=amount_paise,
                    description=description,
                )

        self.stdout.write(self.style.SUCCESS("Seed data created successfully."))
