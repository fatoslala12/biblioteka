#!/usr/bin/env bash
# Krijon superuser pa dialog (Django 3+).
#
# Përdorim lokal (nga rrënja e projektit):
#   export DJANGO_SUPERUSER_USERNAME=admin
#   export DJANGO_SUPERUSER_EMAIL=ti@example.com
#   export DJANGO_SUPERUSER_PASSWORD='fjalekalim-i-forte'
#   bash scripts/create_superuser.sh
#
# Në server (SSH), një rresht (zgjidh imazhin e duhur nëse emri ndryshon):
#   CID=$(docker ps -q --filter ancestor=biblioteka-webapp-zbhcrr:latest)
#   docker exec -e DJANGO_SUPERUSER_USERNAME=admin -e DJANGO_SUPERUSER_EMAIL=ti@example.com \
#     -e DJANGO_SUPERUSER_PASSWORD='fjalekalimi' "$CID" \
#     /opt/venv/bin/python manage.py createsuperuser --noinput
set -euo pipefail
cd "$(dirname "$0")/.."
# Nixpacks/Dokploy: Django është në /opt/venv, jo në python të sistemit.
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
if [ -x /opt/venv/bin/python ]; then PY=/opt/venv/bin/python; fi
: "${DJANGO_SUPERUSER_USERNAME:?Vendos DJANGO_SUPERUSER_USERNAME}"
: "${DJANGO_SUPERUSER_EMAIL:?Vendos DJANGO_SUPERUSER_EMAIL}"
: "${DJANGO_SUPERUSER_PASSWORD:?Vendos DJANGO_SUPERUSER_PASSWORD}"
"$PY" manage.py createsuperuser --noinput \
  --username="$DJANGO_SUPERUSER_USERNAME" \
  --email="$DJANGO_SUPERUSER_EMAIL"
echo "OK: superuser '$DJANGO_SUPERUSER_USERNAME' u krijua (nëse nuk ekzistonte më parë)."
