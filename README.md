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
