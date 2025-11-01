import sys

from django.apps import AppConfig
from django.conf import settings


def _should_start_scheduler() -> bool:
    if not getattr(settings, 'UNICRM_AUTO_START_SCHEDULER', True):
        return False

    if not sys.argv:
        return False

    entrypoint = sys.argv[0] or ''

    if entrypoint.endswith('manage.py'):
        return len(sys.argv) > 1 and sys.argv[1] == 'runserver'

    server_names = ('daphne', 'gunicorn', 'uvicorn')
    return any(name in entrypoint for name in server_names)


class UnicrmConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'unicrm'

    def ready(self):
        from . import signals  # noqa: F401

        if _should_start_scheduler():
            from unicrm.services.communication_runner import communication_scheduler_runner

            interval = getattr(settings, 'UNICRM_SCHEDULER_INTERVAL', 10)
            communication_scheduler_runner.start(interval=interval)
