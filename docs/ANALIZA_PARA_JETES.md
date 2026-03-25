# Analizë e plotë — Smart Library (para nisjes live)

Dokumenti mbulon **4 fusha**: Design, Logjikë & Workflow, Funksionalitete, Optimizim — me sugjerime konkrete para se ta nisni sistemin live.

---

## 1. DESIGN

### 1.1 Çfarë funksionon mirë
- **Faqja publike (CMS)**: Tailwind CDN, font Inter, paleta brand (teal #319088), dark mode, skeleton/toast, loading bar — pamje e pastër dhe moderne.
- **Admin (Jazzmin)**: Dashboard i njësuar me karta, grafikë Chart.js, seksione me titull me vijë gradient; paleta e qëndrueshme.
- **Baza e përbashkët**: `base.html` me header/footer të qëndrueshëm, theme toggle, strukturë e qartë.

### 1.2 Sugjerime design

| Prioritet | Sugjerim | Detaj |
|----------|----------|--------|
| **Lart** | **Navigimi në mobile** | Nav kryesor është `hidden` në ekrane të vogla (`md:flex`). Në telefon përdoruesit nuk shohin Katalog, Njoftime, Kontakt, etj. **Veprim**: Shtoni një menu hamburger (buton + dropdown/drawer) që hap të njëjtat linke në mobile. |
| **Lart** | **Favicon** | Vendosni `<link rel="icon" href="{% static 'img/favicon.ico' %}">` në `base.html` që faqja të ketë ikonë në tab. |
| **Mes** | **Meta Open Graph / Twitter** | Për ndarje në rrjetet sociale, shtoni `og:title`, `og:description`, `og:image` (dhe tw:*) në faqet kryesore (home, katalog, libër). |
| **Mes** | **Faqe 404 / 500** | Nuk ka `handler404`/`handler500` në `urls.py`. Në prod do të shfaqet faqja e parazgjedhur e Django. Krijoni `templates/404.html` dhe `500.html` me stilin e faqes dhe regjistroni handler-at. |
| **Ulet** | **Skip link për aksesueshmëri** | Një "Kalo në përmbajtje" që fokuson `<main>` për përdorues me tastierë/screen reader. |
| **Ulet** | **Kohëzgjatja e session-it** | Nëse dëshironi që përdoruesit të mos dalin shpesh, mund të rrisni `SESSION_COOKIE_AGE` dhe të vendosni `SESSION_SAVE_EVERY_REQUEST = True`. |

---

## 2. LOGJIKË DHE WORKFLOW

### 2.1 Arkitektura e përgjithshme
- **Role**: `User.role` (ADMIN, STAFF, MEMBER) + `MemberProfile` për anëtarë; ndarja admin (/admin/) vs panel (/panel/) vs portal anëtari (/anetar/) është e qartë.
- **Qarkullim**: Loan → Copy (status), Hold (radhë), Reservation (data marrje/dorëzim), ReservationRequest (kërkesë anëtari). Rregullat janë në `policies` dhe `circulation.services`.
- **Admin guard**: `AdminAccessGuardMiddleware` ndalon anëtarët nga /admin/ dhe i ridrejton në /anetar/ — logjikë e shëndoshë.

### 2.2 Sugjerime logjikë dhe workflow

| Prioritet | Sugjerim | Detaj |
|----------|----------|--------|
| **Lart** | **Krahasim role në `book_detail`** | Në `cms/views.py` për `pending_request`/`approved_request` përdoret `request.user.role == "MEMBER"` (string). Në `accounts` përdoret `UserRole.MEMBER`. **Veprim**: Përdorni `request.user.role == UserRole.MEMBER` (ose `str(request.user.role)`) për të qenë konsistent dhe të shmangni gabime nëse ndryshon enum. |
| **Lart** | **Konfirmim para veprimesh destructive** | Në admin, fshirja e Huazimeve/Rezervimeve/Librave — sigurohuni që Django tregon "A jeni të sigurt?" (zakonisht po). Për veprime me impact të madh (p.sh. flush_except_admin) mbani `--no-input` vetëm për skripta. |
| **Mes** | **Duplicate `class Meta` në `Loan`** | Në `circulation/models.py`, modeli `Loan` e ka `class Meta` dy herë. Hiqni njërin për të shmangur konfuzionin. |
| **Mes** | **Redirect pas login** | `_login_default_destination` dhe `_safe_next_for_user` janë të qarta; anëtarët nuk ridrejtohen në /admin/. Kontrolloni që parametri `?next=` të sanitizohet kudo (tashmë bëhet me `url_has_allowed_host_and_scheme`). |
| **Mes** | **Statusi i kopjes pas kthimit** | Kur një huazim kthehet, Copy duhet të kalojë në AVAILABLE (ose në ON_HOLD nëse ka hold për atë libër). Verifikoni që ky tranzicion bëhet në formën e kthimit / në `save()` të Loan. |
| **Ulet** | **Audit për veprime kritike** | Ekziston `audit.services.log_audit_event`; përdoret në portal anëtari. Mund të shtoni audit edhe për huazim/kthim nga stafi (në admin ose panel) për gjurmueshmëri. |

---

## 3. FUNKSIONALITETE

### 3.1 Çfarë ofrohet
- **Faqja publike**: Home, Katalog (kërkim + filtra), detaj libri, Njoftime, Evente, Video, Rreth nesh, Rregullore, Orar, Kontakt (formë + ruajtje + email).
- **Autentifikim**: Hyrje/Dalje, portal anëtari (huazime, rezervime, kërkesa, profil, ndërrim fjalëkalimi), bllokim llogarie.
- **Admin**: Libra, kopje, autorë, zhanre, huazime, rezervime, kërkesa rezervimesh, gjoba, raporte Excel/PDF me filtra (datë, libër, autor, anëtar), dashboard me analitikë.
- **Panel stafi**: `/panel/` për libra dhe kopje, profili anëtarëve (nëse përdoret).
- **API**: REST me JWT (libra, kopje, huazime, hold, policies), dokumentacion Swagger.

### 3.2 Sugjerime funksionalitete

| Prioritet | Sugjerim | Detaj |
|----------|----------|--------|
| **Lart** | **Email në prod** | `EMAIL_BACKEND` është `console`. Për live, konfiguroni SMTP (ose provider si SendGrid/Mailgun) dhe `DEFAULT_FROM_EMAIL`; përndryshe mesazhet e kontaktit dhe njoftimet e anëtarëve nuk dërgohen. |
| **Lart** | **Recovery fjalëkalimi** | Nuk ka faqe "Harruat fjalëkalimin?". Django ofron `PasswordResetView`; shtoni URL dhe template (ose përdorni Jazzmin) dhe lidhni nga faqja e hyrjes. |
| **Mes** | **Kufizim tentativash hyrje** | Për të zvogëluar brute-force, mund të shtoni `django-axes` ose rate limiting në faqen e login (p.sh. me cache). |
| **Mes** | **Eksport i madh** | Excel/PDF për huazime/rezervime/gjoba janë të filtruara; nëse përdoruesi zgjedh një interval shumë të madh, mund të keni mijëra rreshta. Konsideroni limit (p.sh. max 5000 rreshta) ose raport asinkron (Celery) për eksporte të mëdha. |
| **Mes** | **Notifikime anëtari** | Email kur: kërkesa e rezervimit pranohet, libri është gati për marrje, afati i kthimit po afrohet, gjobë. Të gjitha këto rrisin përvojën e anëtarit. |
| **Ulet** | **Versione API** | Nëse planifikoni ndryshime të mëdha në API, mund të prezantoni versioning (p.sh. `/api/v1/`) që tashmë pjesërisht ndiqet nga router-at. |
| **Ulet** | **SMS (opsional)** | Për njoftime shumë të rëndësishme (afat kthimi, gati për marrje), mund të integroni një provider SMS (Albanian ose international). |

---

## 4. OPTIMIZIM

### 4.1 Bazat e dhënash dhe query
- **Pika të forta**: `select_related`/`prefetch_related` përdoren në katalog, book_detail, dashboard (admin_stats). Indekset në `Loan` (status, due_at), `Hold` (book, status, position) janë të përshtatshme.
- **Rreziqe**: Faqja e admin dashboard ekzekuton shumë template tags (loans by month, top books/authors/members, fines, copies, due soon, etj.). Çdo kërkesë bën shumë query.

### 4.2 Sugjerime optimizim

| Prioritet | Sugjerim | Detaj |
|----------|----------|--------|
| **Lart** | **Cache për dashboard admin** | Dashboard-i kryen shumë agregime. Vendosni cache (p.sh. `cache.set`/`cache.get` me key `dashboard_stats`, TTL 2–5 minuta) për numrat dhe listat e top; ose përdorni `@cache_page(60)` për të gjithë faqen e index të admin (me kujdes për përdorues të ndryshëm nëse ka të dhëna specifike). |
| **Lart** | **Cache për faqen kryesore** | Home page bën shumë count() dhe listime (featured, recent, announcements, events, videos). Një cache 1–2 minuta për kontekstin e home (ose fragment cache për seksionet) ul ngarkimin në DB. |
| **Mes** | **Pagination në API** | Sigurohuni që listat API (books, copies, loans) kanë pagination të aktivizuar dhe madhësi faqe të arsyeshme (p.sh. 20–50). |
| **Mes** | **Static files në prod** | `DEBUG=False` kërkon `python manage.py collectstatic` dhe shërbyes (WhiteNoise ose CDN) për `/static/`. Kontrolloni `STATIC_ROOT` dhe `STATICFILES_DIRS`. |
| **Mes** | **Sessions** | Në prod, përdorni session backend me DB ose cache (jo file) dhe `SESSION_ENGINE` të përshtatshëm. |
| **Ulet** | **Compression** | Aktivizoni GZip middleware për përgjigje HTML/CSS/JS për të ulur madhësinë e transferimit. |
| **Ulet** | **CDN për Chart.js/Tailwind** | Tashmë përdoren CDN; në prod mund të vendosni një version të fiksuar (me integritet SRI) për siguri dhe stabilitet. |

---

## 5. SIGURIA (checklist para live)

| Kontroll | Veprim |
|----------|--------|
| **DEBUG = False** | Vendosni në `.env` për prod. |
| **SECRET_KEY** | Perdorini një key të gjeneruar dhe mos e committoni në repo. |
| **ALLOWED_HOSTS** | Vendosni domenin(e) e prod (p.sh. `biblioteka.example.com`). |
| **HTTPS** | Aktivizoni SSL; në Django `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`. |
| **CSRF** | Forma përdorin `{% csrf_token %}`; në prod kontrolloni `CSRF_TRUSTED_ORIGINS` nëse përdorni subdomain. |
| **Hashing fjalëkalimesh** | Django përdor PBKDF2 si default; mbetet i përshtatshëm. |
| **Databaza** | Përdorni përdorues DB me të drejta minimale (jo superuser në app); backup të rregullta. |
| **Media/Uploads** | Në prod, shërbeni skedarin nga një shërbyes ose storage (S3-style) me kontroll aksesi. |

---

## 6. CHECKLIST I SHPEJTË PARA GO-LIVE

- [ ] **Design**: Menu mobile (hamburger), favicon, 404/500 me template.
- [ ] **Logjikë**: Rregullimi i krahasimit `UserRole.MEMBER` në book_detail; heqja e Meta të dyfishtë në Loan.
- [ ] **Funksionalitete**: Email SMTP në prod; faqe "Harruat fjalëkalimin?"; (opsional) limit eksporti Excel/PDF.
- [ ] **Optimizim**: Cache për dashboard admin dhe/ose home; collectstatic; session backend për prod.
- [ ] **Siguri**: DEBUG=False, SECRET_KEY e sigurt, ALLOWED_HOSTS, HTTPS dhe cookie secure, CSRF_TRUSTED_ORIGINS nëse duhet.
- [ ] **Test**: Testoni regjistrim/hyrje si anëtar, kërkesë rezervimi, hyrje si staf/admin, eksport Excel/PDF, faqen e kontaktit (dërgim email real në prod).

---

*Dokumenti u përgatit për të dhënat dhe kodin e projektit Smart Library në datën e analizës. Përditësojeni pas ndryshimeve të mëdha.*
