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

### Kalimi në PostgreSQL (më vonë)
Mjafton të vendosësh `DATABASE_URL` në `.env` dhe të bësh `migrate`.
