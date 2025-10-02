from django.apps import AppConfig


class UnicomProjectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'unicom_project'

    def ready(self):
        # Import callback handlers to register signal receivers
        import unicom_project.callback_handlers