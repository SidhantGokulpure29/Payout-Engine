## Payout Engine

Minimal payout engine for merchants receiving INR payouts after international collections.

### Stack

- Backend: Django, Django REST Framework, PostgreSQL
- Background jobs: Celery with Redis
- Frontend: React + Tailwind

### Implemented Backend Features

- Merchant, bank account, payout, ledger, and idempotency data models
- Database-derived balance calculation in paise
- Payout request API shape with idempotency handling
- Transaction-safe payout creation with row locking
- Async payout processor with simulated bank outcomes
- Retry flow for stuck payouts
- Seed data command
- Concurrency and idempotency tests

### Project Structure

- `backend/core`: Django project settings and Celery config
- `backend/payouts`: payout domain models, services, API, tasks, tests

### Setup

1. Create and activate a Python virtual environment.
2. Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Start PostgreSQL and Redis with Docker:

```bash
docker compose up -d
```

4. Set environment variables if needed:

```bash
POSTGRES_DB=playto
POSTGRES_USER=playto
POSTGRES_PASSWORD=playto
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
REDIS_URL=redis://localhost:6379/0
DEBUG=True
SECRET_KEY=dev-secret-key-change-in-prod
```

PowerShell example:

```powershell
$env:POSTGRES_DB='playto'
$env:POSTGRES_USER='playto'
$env:POSTGRES_PASSWORD='playto'
$env:POSTGRES_HOST='localhost'
$env:POSTGRES_PORT='5432'
$env:REDIS_URL='redis://localhost:6379/0'
```

5. Run migrations:

```bash
venv\Scripts\python.exe backend\manage.py makemigrations payouts
venv\Scripts\python.exe backend\manage.py migrate
```

6. Seed sample merchants:

```bash
venv\Scripts\python.exe backend\manage.py seed_data
```

7. Run the Django API:

```bash
venv\Scripts\python.exe backend\manage.py runserver
```

8. Run Celery worker:

```bash
cd backend
..\venv\Scripts\celery.exe -A core worker -l info --pool=solo
```

`--pool=solo` is recommended on Windows.

9. Run Celery beat:

```bash
cd backend
..\venv\Scripts\celery.exe -A core beat -l info
```

### API Endpoints

- `POST /api/v1/payouts`
  - Headers:
    - `X-Merchant-Id: <merchant_uuid>`
    - `Idempotency-Key: <uuid>`
  - Body:

```json
{
  "amount_paise": 2500,
  "bank_account_id": "merchant-bank-account-uuid"
}
```

- `GET /api/v1/merchants/<merchant_id>/dashboard`
- `GET /api/v1/merchants/<merchant_id>/balance`
- `GET /api/v1/merchants/<merchant_id>/ledger`
- `GET /api/v1/merchants/<merchant_id>/payouts`

### Tests

Run:

```bash
venv\Scripts\python.exe backend\manage.py test payouts
```

### Frontend

1. Install frontend dependencies:

```bash
cd frontend
npm install
```

2. Start the dashboard:

```bash
npm run dev
```

3. Optional frontend environment variables:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
VITE_MERCHANT_ID=<seeded-merchant-uuid>
```

### Notes

- All money is stored as `BigIntegerField` in paise.
- Balance is derived from ledger entries, not stored as a mutable field.
- Concurrency protection relies on `transaction.atomic()` + `select_for_update()`.
- Background settlement is simulated with success, failure, and hang outcomes.
- Local development uses Docker-backed PostgreSQL and Redis via [docker-compose.yml](/d:/Notes/All%20Materials/Playto_Pay_Assignment/docker-compose.yml).
