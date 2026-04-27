## Executive Summary

This project is designed around four correctness guarantees:

- no merchant can overdraw available funds during concurrent payout requests
- retries and duplicate client requests do not create duplicate payouts
- payout state transitions are explicit and constrained
- balances are derived from immutable ledger entries rather than mutated counters

The most important engineering choice is that payout creation is treated as a transactional accounting operation, not just an API write. The system locks the merchant row, recomputes available balance from the ledger, creates the payout, and inserts the hold entry in one atomic path. That is what prevents race-condition overdrafts.

For local development, the project supports Celery + Redis. For the live Railway demo, I adapted the background-processing path so the same payout domain logic can run without dedicated worker and beat services. That tradeoff keeps the submission easy to deploy while preserving the concurrency, idempotency, ledger, and state-machine guarantees that matter most.

## 1. The Ledger

Balance is derived from ledger entries, not stored directly on the merchant row.

Current balance query lives in [backend/payouts/services.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/services.py):

```python
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
```

I modeled money movement with `credit`, `hold`, `release`, and `debit` entries because that makes payout reservation explicit:

- `credit`: money added from simulated customer payments
- `hold`: money reserved when a payout is requested
- `release`: money returned if a payout fails
- `debit`: money finalized when a payout completes

This keeps the ledger append-only and makes payout side effects easy to audit.

## 2. The Lock

The exact overdraft-prevention code is in [backend/payouts/services.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/services.py):

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)
    balance = get_merchant_balance(merchant.id)
    if balance.available_balance_paise < amount_paise:
        raise InsufficientBalanceError("Insufficient available balance.")
```

This relies on PostgreSQL row-level locking through `SELECT ... FOR UPDATE`.

Why it matters:
- two concurrent payout requests for the same merchant cannot both pass the balance check at the same time
- the second request waits until the first transaction finishes
- once the first request inserts the hold ledger entry, the second request sees the updated effective balance and fails cleanly if funds are no longer available

## 3. The Idempotency

The system tracks seen idempotency keys in the `IdempotencyKey` table in [backend/payouts/models.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/models.py).

Each record stores:
- `merchant`
- `key`
- `payout`
- `request_fingerprint`
- `expires_at`

The request path is in [backend/payouts/services.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/services.py):

```python
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
```

If the same merchant sends the same key again, the API returns the existing payout instead of creating another one.

If the same key is reused with different request data, it is rejected as a conflict.

If the first request is still in flight, the second request blocks on the same transactional row path and then sees the existing idempotency record instead of creating a duplicate payout.

## 4. The State Machine

The legal transitions are defined in [backend/payouts/models.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/models.py):

```python
LEGAL_TRANSITIONS = {
    Status.PENDING: {Status.PROCESSING},
    Status.PROCESSING: {Status.COMPLETED, Status.FAILED},
    Status.COMPLETED: set(),
    Status.FAILED: set(),
}
```

The enforcement check is:

```python
def transition_to(self, new_status):
    allowed_statuses = self.LEGAL_TRANSITIONS.get(self.status, set())
    if new_status not in allowed_statuses:
        raise ValueError(
            f"Illegal state transition: {self.status} -> {new_status}"
        )
    self.status = new_status
```

That is what blocks illegal paths like `failed -> completed` or `completed -> pending`.

## 5. The AI Audit

One specific place where I did not trust the initial AI-shaped implementation was retry accounting for stuck payouts.

A naive version of the retry flow looked like this:

```python
for payout in get_stuck_payouts():
    payout.attempt_count += 1
    payout.processing_started_at = timezone.now()
    payout.save()
    settle_stuck_payout.apply_async(args=[str(payout.id)], countdown=backoff)
```

The bug is subtle: it burns a retry attempt before the retry worker actually starts. If the scheduled task never runs, the payout can still lose attempts and reach the max-attempt failure path too early.

I replaced that with a two-step approach:
- first mark the stuck payout as ready for retry without consuming an attempt
- increment the attempt only when processing actually restarts

The corrected helper in [backend/payouts/services.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/services.py) is:

```python
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
```

And the retry path only consumes the attempt when work actually resumes:

```python
def settle_stuck_payout(payout_id: str):
    try:
        mark_payout_processing(payout_id=payout_id, increment_attempt=True)
    except (Payout.DoesNotExist, PayoutNotProcessableError):
        return

    _settle_processing_payout(payout_id)
```

That change keeps the "max 3 attempts" invariant honest. Attempts now reflect real processing starts, not merely scheduled retries.

## 6. Deployment Adaptation

One practical issue in the final submission was deployment shape.

The original local architecture supports Celery + Redis, and the async tasks still exist in [backend/payouts/tasks.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/tasks.py). But for the live Railway deployment, I removed the requirement for separate worker and beat services and reused the same domain logic from the web process.

The deployed request path now does this in [backend/payouts/views.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/views.py):

```python
if created:
    transaction.on_commit(
        lambda: trigger_background_payout_processing(payout_id=payout.id)
    )
```

And dashboard-style read endpoints call:

```python
sweep_unprocessed_payouts()
```

The supporting Railway-compatible helper is in [backend/payouts/services.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/services.py):

```python
def trigger_background_payout_processing(
    *,
    payout_id: UUID,
    increment_attempt: bool = True,
):
    thread = threading.Thread(
        target=_run_background_processing,
        args=(payout_id, increment_attempt),
        daemon=True,
    )
    thread.start()
```

Why I kept this version for deployment:
- the assignment remains easy to run on Railway without provisioning extra always-on services
- payout creation is still transactional and idempotent
- simulated async behavior is preserved for the user-facing dashboard
- stuck payouts still get another chance via the sweep path on later reads

Tradeoff:
- this is less production-grade than a dedicated queue worker setup because it leans on the web process
- for the assignment submission, it dramatically simplifies hosting while keeping the concurrency, idempotency, ledger, and payout-state guarantees intact
