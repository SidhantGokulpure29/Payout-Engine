from celery import shared_task

from payouts.models import Payout
from payouts.services import (
    mark_stuck_payout_ready_for_retry,
    PayoutNotProcessableError,
    choose_settlement_outcome,
    complete_payout,
    fail_payout,
    get_stuck_payouts,
    mark_payout_processing,
)


def _settle_processing_payout(payout_id: str):
    outcome = choose_settlement_outcome()

    if outcome == "success":
        try:
            complete_payout(payout_id=payout_id)
        except (Payout.DoesNotExist, PayoutNotProcessableError):
            return
        return

    if outcome == "failure":
        try:
            fail_payout(
                payout_id=payout_id,
                reason="Simulated bank settlement failure.",
            )
        except (Payout.DoesNotExist, PayoutNotProcessableError):
            return
        return


@shared_task
def process_payout(payout_id: str):
    try:
        mark_payout_processing(payout_id=payout_id)
    except (Payout.DoesNotExist, PayoutNotProcessableError):
        return

    _settle_processing_payout(payout_id)


@shared_task
def enqueue_pending_payouts():
    pending_ids = list(
        Payout.objects.filter(status=Payout.Status.PENDING).values_list("id", flat=True)
    )
    for payout_id in pending_ids:
        process_payout.delay(str(payout_id))


@shared_task
def retry_stuck_payouts():
    for payout in get_stuck_payouts():
        if payout.attempt_count >= 3:
            try:
                fail_payout(
                    payout_id=payout.id,
                    reason="Payout failed after maximum retry attempts.",
                )
            except (Payout.DoesNotExist, PayoutNotProcessableError):
                continue
            continue

        countdown_seconds = 2 ** payout.attempt_count
        try:
            mark_stuck_payout_ready_for_retry(payout_id=payout.id)
        except (Payout.DoesNotExist, PayoutNotProcessableError):
            continue

        settle_stuck_payout.apply_async(
            args=[str(payout.id)],
            countdown=countdown_seconds,
        )


@shared_task
def settle_stuck_payout(payout_id: str):
    try:
        mark_payout_processing(payout_id=payout_id, increment_attempt=True)
    except (Payout.DoesNotExist, PayoutNotProcessableError):
        return

    _settle_processing_payout(payout_id)
