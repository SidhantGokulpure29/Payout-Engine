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

One subtle issue I caught was around retrying stuck payouts.

A naive AI-generated approach would often do something like:

```python
for payout in get_stuck_payouts():
    payout.attempt_count += 1
    payout.processing_started_at = timezone.now()
    payout.save()
    settle_stuck_payout.apply_async(args=[str(payout.id)], countdown=backoff)
```

That looks convenient, but it burns retry attempts before the retry task actually starts. If Celery fails to execute the scheduled retry, the payout can still lose an attempt and reach max-attempt failure too early.

I replaced that with a safer retry flow:
- keep the payout in `processing`
- mark it ready for retry without incrementing `attempt_count`
- increment the attempt only when the retry worker actually starts processing

The retry helpers now live in [backend/payouts/services.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/services.py) and [backend/payouts/tasks.py](/d:/Notes/All%20Materials/Playto_Pay_Assignment/backend/payouts/tasks.py):

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
        payout.save(...)
        return payout
```

And then the retry task starts processing and consumes the attempt:

```python
def settle_stuck_payout(payout_id: str):
    mark_payout_processing(payout_id=payout_id, increment_attempt=True)
    _settle_processing_payout(payout_id)
```

This keeps retries explainable and makes the "max 3 attempts" rule reflect real processing attempts rather than just scheduled retries.
