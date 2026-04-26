from django.urls import path

from payouts.views import (
    MerchantBalanceView,
    MerchantDashboardView,
    MerchantLedgerView,
    MerchantPayoutListView,
    PayoutCreateView,
)


urlpatterns = [
    path("payouts", PayoutCreateView.as_view(), name="payout-create"),
    path(
        "merchants/<uuid:merchant_id>/dashboard",
        MerchantDashboardView.as_view(),
        name="merchant-dashboard",
    ),
    path(
        "merchants/<uuid:merchant_id>/balance",
        MerchantBalanceView.as_view(),
        name="merchant-balance",
    ),
    path(
        "merchants/<uuid:merchant_id>/ledger",
        MerchantLedgerView.as_view(),
        name="merchant-ledger",
    ),
    path(
        "merchants/<uuid:merchant_id>/payouts",
        MerchantPayoutListView.as_view(),
        name="merchant-payouts",
    ),
]
