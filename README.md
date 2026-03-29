## Smart Library (MVP)

Backend (API + Admin panel) për menaxhim librash/kopjesh, huazime, rezervime dhe gjoba.

### Kërkesa
- Python 3.12+

### Setup lokal

Krijo `.env`:

```bash
copy .env.example .env
```

Instalo varësitë:

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

Krijo DB + migrime:

```bash
.venv\Scripts\python manage.py migrate
```

Krijo admin user:

```bash
.venv\Scripts\python manage.py createsuperuser
```

Start server:

```bash
.venv\Scripts\python manage.py runserver
```

### URL të dobishme
- Admin: `http://127.0.0.1:8000/admin/`
- API docs (OpenAPI/Swagger): `http://127.0.0.1:8000/api/docs/`

### Operime ditore (ops)

Komanda raporti:

```bash
.venv\Scripts\python manage.py daily_ops_report
```

Output JSON:

```bash
.venv\Scripts\python manage.py daily_ops_report --json
```

Ruaj raportin në file:

```bash
.venv\Scripts\python manage.py daily_ops_report --save-file docs\ops-reports\daily_ops.json
```

Dërgo raportin me email:

```bash
.venv\Scripts\python manage.py daily_ops_report --send-email --email-to ops@example.com
```

ose përdor `OPS_REPORT_RECIPIENTS` në `.env` dhe thjesht:

```bash
.venv\Scripts\python manage.py daily_ops_report --send-email
```

Alert pragje (threshold) për prioritet të lartë:

```bash
.venv\Scripts\python manage.py daily_ops_report --send-email --threshold-overdue-loans 5 --threshold-overdue-reservations 3 --threshold-pending-requests 10 --threshold-unpaid-fines-total 500.00
```

Nivelet e prioritetit:
- `MEDIUM` (afër pragut, ~75%)
- `HIGH` (pragu i kaluar)
- `CRITICAL` (>= 2x pragut)

Email subject ndryshon automatikisht:
- `[MEDIUM PRIORITY] ...`
- `[HIGH PRIORITY] ...`
- `[CRITICAL PRIORITY] ...`

Raporti përfshin edhe seksionin `Action Needed Today`.
Pragjet default mund t’i vendosësh në `.env`:
- `OPS_ALERT_OVERDUE_LOANS_THRESHOLD`
- `OPS_ALERT_OVERDUE_RESERVATIONS_THRESHOLD`
- `OPS_ALERT_PENDING_REQUESTS_THRESHOLD`
- `OPS_ALERT_UNPAID_FINES_TOTAL_THRESHOLD`

Njoftime automatike për anëtarët (email/SMS):

```bash
.venv\Scripts\python manage.py notify_members --channels both
```

Email-et dërgohen në format **HTML premium** + fallback text.

Dry-run pa dërgim real:

```bash
.venv\Scripts\python manage.py notify_members --channels email --dry-run
```

Konfigurime njoftimesh në `.env`:
- `NOTIFY_DUE_SOON_DAYS`
- `NOTIFY_FINE_CREATED_LOOKBACK_DAYS`
- `NOTIFY_RESERVATION_EXPIRY_HOURS`
- `SMS_WEBHOOK_URL`
- `SMS_WEBHOOK_TOKEN`

Auto-expire rezervimesh:

```bash
.venv\Scripts\python manage.py expire_reservations
```

Windows scheduler helper script:

```bash
scripts\daily_ops_report.bat
```

Për ta planifikuar çdo ditë në Windows Task Scheduler:
- Program/script: `cmd.exe`
- Add arguments: `/c "C:\rruga\te\projekti\scripts\daily_ops_report.bat"`
- Trigger: Daily (p.sh. 08:00)

### Kalimi në PostgreSQL (më vonë)
Mjafton të vendosësh `DATABASE_URL` në `.env` dhe të bësh `migrate`.
