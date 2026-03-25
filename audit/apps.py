from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = "Auditim"

    def ready(self):
        # Register auth/login audit listeners.
        from . import signals  # noqa: F401
