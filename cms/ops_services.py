from __future__ import annotations

import gzip
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import django
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone as dj_timezone


def backup_dir() -> Path:
    raw = (getattr(settings, "OPS_BACKUP_DIR", "") or "").strip()
    if raw:
        path = Path(raw)
    else:
        path = Path(settings.BASE_DIR) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _bytes_to_gb(num: int | float) -> float:
    return round(float(num) / (1024 ** 3), 2)


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def disk_usage_for(path: Path) -> dict:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return {
            "path": str(path),
            "total_gb": None,
            "used_gb": None,
            "free_gb": None,
            "percent": None,
            "ok": False,
        }
    percent = round((usage.used / usage.total) * 100, 1) if usage.total else 0
    return {
        "path": str(path),
        "total_gb": _bytes_to_gb(usage.total),
        "used_gb": _bytes_to_gb(usage.used),
        "free_gb": _bytes_to_gb(usage.free),
        "percent": percent,
        "ok": True,
    }


def _db_engine() -> str:
    return connection.settings_dict.get("ENGINE", "")


def _is_postgresql() -> bool:
    return "postgresql" in _db_engine()


def _is_sqlite() -> bool:
    return "sqlite" in _db_engine()


def database_status() -> dict:
    out = {
        "connected": False,
        "status_label": "Disconnected",
        "status_class": "danger",
        "name": "",
        "engine": _db_engine().rsplit(".", maxsplit=1)[-1],
        "version": "",
        "size_human": "",
        "size_bytes": 0,
        "host": "",
    }
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if _is_postgresql():
                cursor.execute("SELECT current_database()")
                out["name"] = cursor.fetchone()[0]
                cursor.execute("SELECT version()")
                out["version"] = (cursor.fetchone()[0] or "").split(",")[0]
                cursor.execute("SELECT pg_database_size(current_database())")
                size_bytes = int(cursor.fetchone()[0])
                out["size_bytes"] = size_bytes
                cursor.execute("SELECT pg_size_pretty(%s::bigint)", [size_bytes])
                out["size_human"] = cursor.fetchone()[0]
                out["host"] = connection.settings_dict.get("HOST") or "localhost"
            elif _is_sqlite():
                db_path = connection.settings_dict.get("NAME")
                out["name"] = Path(str(db_path)).name
                out["version"] = f"SQLite {sqlite_version(cursor)}"
                if db_path and Path(str(db_path)).exists():
                    out["size_bytes"] = Path(str(db_path)).stat().st_size
                    out["size_human"] = _human_size(out["size_bytes"])
                out["host"] = "local"
            else:
                out["name"] = connection.settings_dict.get("NAME", "")
                out["version"] = out["engine"]
        out["connected"] = True
        out["status_label"] = "Connected"
        out["status_class"] = "success"
    except Exception as exc:
        out["error"] = str(exc)
    return out


def sqlite_version(cursor) -> str:
    try:
        cursor.execute("SELECT sqlite_version()")
        return cursor.fetchone()[0]
    except Exception:
        return ""


def _human_size(num: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num} B"


def web_application_status() -> dict:
    pending: list[tuple[str, str]] = []
    try:
        executor = MigrationExecutor(connection)
        pending = [(app, name) for app, name in executor.migration_plan(executor.loader.graph.leaf_nodes())]
    except Exception:
        pending = []

    email_ok = bool(getattr(settings, "EMAIL_HOST_USER", "") and getattr(settings, "EMAIL_HOST_PASSWORD", ""))
    return {
        "django_version": django.get_version(),
        "python_version": platform.python_version(),
        "debug": bool(getattr(settings, "DEBUG", False)),
        "maintenance_mode": bool(getattr(settings, "MAINTENANCE_MODE", False)),
        "allowed_hosts_count": len(getattr(settings, "ALLOWED_HOSTS", []) or []),
        "pending_migrations": len(pending),
        "pending_migration_labels": [f"{app}.{name}" for app, name in pending[:8]],
        "email_configured": email_ok,
        "public_base_url": (getattr(settings, "PUBLIC_BASE_URL", "") or "").strip(),
        "status_label": "Online" if not pending else "Needs migration",
        "status_class": "success" if not pending else "warning",
    }


def storage_overview() -> dict:
    media_root = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))
    static_root = Path(getattr(settings, "STATIC_ROOT", settings.BASE_DIR / "staticfiles"))
    backups = backup_dir()
    return {
        "project_disk": disk_usage_for(Path(settings.BASE_DIR)),
        "media": {
            "path": str(media_root),
            "size_human": _human_size(_dir_size(media_root)),
            "size_bytes": _dir_size(media_root),
        },
        "staticfiles": {
            "path": str(static_root),
            "size_human": _human_size(_dir_size(static_root)),
            "size_bytes": _dir_size(static_root),
        },
        "backups": {
            "path": str(backups),
            "size_human": _human_size(_dir_size(backups)),
            "size_bytes": _dir_size(backups),
        },
    }


_TABLE_ICONS = {
    "accounts": "fa-users",
    "catalog": "fa-book",
    "circulation": "fa-exchange-alt",
    "cms": "fa-bullhorn",
    "fines": "fa-receipt",
    "notifications": "fa-bell",
    "policies": "fa-sliders-h",
    "audit": "fa-clipboard-list",
    "auth": "fa-key",
}


def database_table_stats() -> list[dict]:
    rows: list[dict] = []
    for model in apps.get_models():
        if not model._meta.managed or model._meta.proxy:
            continue
        label = model._meta.label_lower
        try:
            count = model.objects.count()
        except Exception:
            count = None
        app_label = model._meta.app_label
        rows.append(
            {
                "label": str(model._meta.verbose_name_plural or model._meta.verbose_name or label),
                "table": model._meta.db_table,
                "app": app_label,
                "count": count,
                "icon": _TABLE_ICONS.get(app_label, "fa-database"),
            }
        )
    rows.sort(key=lambda item: (-1 if item["count"] is None else item["count"], item["label"]))
    return rows


def list_backups() -> list[dict]:
    out: list[dict] = []
    root = backup_dir()
    for path in sorted(root.glob("backup-*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        stat = path.stat()
        out.append(
            {
                "filename": path.name,
                "size_human": _human_size(stat.st_size),
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            }
        )
    return out


def _safe_backup_name(filename: str) -> Path | None:
    name = os.path.basename((filename or "").strip())
    if not name or name != filename:
        return None
    if not (name.startswith("backup-") and (name.endswith(".sql") or name.endswith(".sql.gz") or name.endswith(".sqlite3.gz"))):
        return None
    path = backup_dir() / name
    if not path.is_file():
        return None
    return path


def create_full_backup(description: str = "") -> dict:
    stamp = dj_timezone.now().strftime("%Y-%m-%dT%H-%M-%S")
    root = backup_dir()
    desc_slug = "".join(ch for ch in (description or "").strip().lower() if ch.isalnum() or ch in "-_")[:40]
    suffix = f"-{desc_slug}" if desc_slug else ""

    if _is_postgresql():
        filename = f"backup-full-{stamp}{suffix}.sql.gz"
        target = root / filename
        db = connection.settings_dict
        env = os.environ.copy()
        if db.get("PASSWORD"):
            env["PGPASSWORD"] = str(db["PASSWORD"])
        cmd = [
            "pg_dump",
            "-h",
            str(db.get("HOST") or "localhost"),
            "-p",
            str(db.get("PORT") or "5432"),
            "-U",
            str(db.get("USER") or "postgres"),
            "-d",
            str(db.get("NAME") or ""),
            "--no-owner",
            "--no-acl",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, env=env, check=False, timeout=300)
        except FileNotFoundError:
            return {"ok": False, "error": "pg_dump nuk u gjet në server."}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Backup-i zgjati shumë dhe u ndal."}
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            return {"ok": False, "error": err or "pg_dump dështoi."}
        with gzip.open(target, "wb") as fh:
            fh.write(proc.stdout)
    elif _is_sqlite():
        import sqlite3

        filename = f"backup-full-{stamp}{suffix}.sqlite3.gz"
        target = root / filename
        tmp_path = root / f".tmp-backup-{stamp}.sqlite3"
        db_name = str(connection.settings_dict.get("NAME") or "")
        try:
            db_file = Path(db_name)
            if db_file.is_file():
                with gzip.open(target, "wb") as out_fh, open(db_file, "rb") as in_fh:
                    shutil.copyfileobj(in_fh, out_fh)
            elif db_name:
                with sqlite3.connect(db_name, timeout=30) as src_conn, sqlite3.connect(str(tmp_path)) as dest_conn:
                    src_conn.backup(dest_conn)
                with gzip.open(target, "wb") as out_fh, open(tmp_path, "rb") as in_fh:
                    shutil.copyfileobj(in_fh, out_fh)
            else:
                return {"ok": False, "error": "Skedari SQLite nuk u gjet."}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
    else:
        return {"ok": False, "error": "Motor i panjohur databaze për backup."}

    return {
        "ok": True,
        "filename": filename,
        "path": str(target),
        "size_human": _human_size(target.stat().st_size),
    }


def delete_backup(filename: str) -> dict:
    path = _safe_backup_name(filename)
    if not path:
        return {"ok": False, "error": "Backup-i nuk u gjet."}
    path.unlink(missing_ok=True)
    return {"ok": True, "filename": filename}


def clean_old_backups(days: int | None = None) -> dict:
    keep_days = days if days is not None else int(getattr(settings, "OPS_BACKUP_RETENTION_DAYS", 14) or 14)
    cutoff = dj_timezone.now() - timedelta(days=max(keep_days, 1))
    removed: list[str] = []
    for item in list_backups():
        created = item["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < cutoff:
            path = _safe_backup_name(item["filename"])
            if path:
                path.unlink(missing_ok=True)
                removed.append(item["filename"])
    return {"ok": True, "removed": removed, "count": len(removed), "retention_days": keep_days}


def operational_summary() -> dict:
    from django.contrib.admin.models import LogEntry
    from django.contrib.sessions.models import Session
    from django.urls import reverse

    from cms.models import ContactMessage
    from circulation.models import Loan, LoanStatus, ReservationRequest, ReservationRequestStatus

    now = dj_timezone.now()
    disk = disk_usage_for(Path(settings.BASE_DIR))
    disk_percent = disk.get("percent")
    disk_level = "normal"
    if disk_percent is not None:
        if disk_percent >= 90:
            disk_level = "critical"
        elif disk_percent >= 80:
            disk_level = "warning"

    return {
        "contact_unread": ContactMessage.objects.filter(is_read=False).count(),
        "contact_unreplied": ContactMessage.objects.filter(is_replied=False).count(),
        "pending_requests": ReservationRequest.objects.filter(status=ReservationRequestStatus.PENDING).count(),
        "overdue_loans": Loan.objects.filter(status=LoanStatus.ACTIVE, due_at__lt=now).count(),
        "active_sessions": Session.objects.count(),
        "admin_log_entries": LogEntry.objects.count(),
        "disk_level": disk_level,
        "disk_percent": disk_percent,
        "urls": {
            "contact_unread": f"{reverse('admin:cms_contactmessage_changelist')}?status=unread",
            "contact_all": reverse("admin:cms_contactmessage_changelist"),
            "pending_requests": reverse("admin:circulation_reservationrequest_changelist"),
            "overdue_loans": reverse("admin:circulation_loan_changelist"),
        },
    }


def clear_expired_sessions() -> dict:
    from django.contrib.sessions.models import Session

    before = Session.objects.count()
    Session.objects.filter(expire_date__lt=dj_timezone.now()).delete()
    after = Session.objects.count()
    return {"ok": True, "removed": max(0, before - after), "remaining": after}


def prune_old_admin_logs(days: int | None = None) -> dict:
    from django.contrib.admin.models import LogEntry

    keep_days = days if days is not None else int(getattr(settings, "OPS_ADMIN_LOG_RETENTION_DAYS", 90) or 90)
    cutoff = dj_timezone.now() - timedelta(days=max(keep_days, 7))
    qs = LogEntry.objects.filter(action_time__lt=cutoff)
    removed = qs.count()
    qs.delete()
    return {"ok": True, "removed": removed, "retention_days": keep_days}


def optimize_database() -> dict:
    try:
        if _is_postgresql():
            with connection.cursor() as cursor:
                cursor.execute("ANALYZE")
            return {"ok": True, "message": "PostgreSQL ANALYZE u ekzekutua."}
        if _is_sqlite():
            with connection.cursor() as cursor:
                cursor.execute("VACUUM")
            return {"ok": True, "message": "SQLite VACUUM u ekzekutua."}
        return {"ok": False, "error": "Optimizimi nuk mbështetet për këtë motor DB."}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def system_settings_context() -> dict:
    db = database_status()
    web = web_application_status()
    storage = storage_overview()
    summary = operational_summary()
    return {
        "db": db,
        "web": web,
        "storage": storage,
        "summary": summary,
        "tables": database_table_stats(),
        "backups": list_backups(),
        "backup_dir": str(backup_dir()),
        "backup_dir_ok": backup_dir().exists(),
        "backup_retention_days": int(getattr(settings, "OPS_BACKUP_RETENTION_DAYS", 14) or 14),
        "admin_log_retention_days": int(getattr(settings, "OPS_ADMIN_LOG_RETENTION_DAYS", 90) or 90),
    }
