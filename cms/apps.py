from django.apps import AppConfig


class CmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cms'
    verbose_name = "Përmbajtje"

    def ready(self):
        from cms import admin_ops

        admin_ops.register_admin_ops_urls()
