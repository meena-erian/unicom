from django.apps import AppConfig


class UnicomConfig(AppConfig):
    name = 'unicom'

    def ready(self):
        from unicom.services.email.IMAP_thread_manager import imap_manager
        import unicom.signals
        imap_manager.start_all()
