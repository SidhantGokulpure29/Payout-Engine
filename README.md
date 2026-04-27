## Payout Engine

Minimal payout engine for merchants receiving INR payouts after international collections.

### Stack

- Backend: Django, Django REST Framework, PostgreSQL
- Async processing: Celery + Redis for local development, Railway-compatible inline background processing for the deployed demo
- Frontend: React + Tailwind

### Live Demo

- Frontend: `https://frontend-service-production-e89e.up.railway.app`
- Backend: `https://splendid-heart-production-8051.up.railway.app`

### Implemented Backend Features

- Merchant, bank account, payout, ledger, and idempotency data models
- Database-derived balance calculation in paise
- Payout request API shape with idempotency handling
- Transaction-safe payout creation with row locking
- Async payout processor with simulated bank outcomes
- Retry flow for stuck payouts
- Railway-friendly deployment path that avoids separate worker/beat services
- Seed data command
- Concurrency and idempotency tests

### Project Structure

- `backend/core`: Django project settings and Celery config
- `backend/payouts`: payout domain models, services, API, tasks, tests

### Setup

Local development supports the full Celery + Redis flow. The deployed Railway version uses the same payout domain logic, but processes background work through the web service so the assignment can run on a simpler free-plan footprint.

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

8. Optional: run Celery worker for the full local async flow:

```bash
cd backend
..\venv\Scripts\celery.exe -A core worker -l info --pool=solo
```

`--pool=solo` is recommended on Windows.

9. Optional: run Celery beat for retry scheduling:

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

### Deployment

The repository includes [render.yaml](/d:/Notes/All%20Materials/Playto_Pay_Assignment/render.yaml) for Render, and the app is also ready for a straightforward Railway deployment.

Recommended Railway layout:

- PostgreSQL service
- Django web service
- Frontend web service

The current deployed version intentionally does not require separate Railway worker or beat services. On Railway, payout processing is triggered after payout creation and stuck payouts are swept during dashboard reads, which keeps the deployment small while preserving the core assignment behavior.

Backend service settings on Railway:

- Root directory: `backend`
- Build command:

```bash
pip install -r requirements.txt && python manage.py migrate
```

- Start command:

```bash
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
```

Frontend service settings on Railway:

- Root directory: `frontend`
- Build command:

```bash
npm install && npm run build
```

- Start command:

```bash
npm run start
```

Backend environment variables for Railway:

```bash
DEBUG=False
SECRET_KEY=<secure-random-value>
ALLOWED_HOSTS=<your-backend-domain>
DATABASE_URL=<railway-postgres-database-url>
CORS_ALLOWED_ORIGINS=https://<your-frontend-domain>
CSRF_TRUSTED_ORIGINS=https://<your-frontend-domain>
```

Frontend environment variables for Railway:

```bash
VITE_API_BASE_URL=https://<your-backend-domain>/api/v1
VITE_MERCHANT_ID=<seeded-merchant-uuid>
```

After the first backend deploy, seed sample data:

```bash
python manage.py seed_data
```

The command prints the seeded merchant UUIDs. Copy one of them into `VITE_MERCHANT_ID` for the frontend.

If the frontend is served with `vite preview`, Railway must have a public generated domain and Vite must allow Railway hosts. That configuration is already included in [frontend/vite.config.js](/d:/Notes/All%20Materials/Playto_Pay_Assignment/frontend/vite.config.js).

### Notes

- All money is stored as `BigIntegerField` in paise.
- Balance is derived from ledger entries, not stored as a mutable field.
- Concurrency protection relies on `transaction.atomic()` + `select_for_update()`.
- Background settlement is simulated with success, failure, and hang outcomes.
- On Railway, background settlement is handled without dedicated worker services to keep the deployment assignment-friendly.
- Local development uses Docker-backed PostgreSQL and Redis via [docker-compose.yml](/d:/Notes/All%20Materials/Playto_Pay_Assignment/docker-compose.yml).
