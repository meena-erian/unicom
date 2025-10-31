from django.apps import AppConfig


class UnicrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'unicrm'

    def ready(self):
        # Import signal handlers
        from . import signals  # noqa: F401
