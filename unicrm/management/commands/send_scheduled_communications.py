from __future__ import annotations

import logging
import time

from django.core.management.base import BaseCommand

from unicrm.services.communication_dispatcher import process_scheduled_communications

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Continuously process scheduled unicrm Communications and send their drafts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=10,
            help='Interval in seconds between scheduler cycles (default: 10).'
        )
        parser.add_argument(
            '--run-once',
            action='store_true',
            help='Process a single cycle and exit.'
        )

    def handle(self, *args, **options):
        interval = max(options['interval'], 1)
        run_once = options['run_once']

        if run_once:
            summary = process_scheduled_communications()
            self._log_summary(summary)
            return

        self.stdout.write(self.style.SUCCESS(
            f'Starting unicrm communication scheduler with a {interval}-second interval...'
        ))

        try:
            while True:
                summary = process_scheduled_communications()
                self._log_summary(summary)
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Scheduler interrupted; shutting down.'))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception('Unicrm scheduler encountered a fatal error: %s', exc)
            raise

    def _log_summary(self, summary):
        processed = summary.get('communications_processed', 0)
        sent = summary.get('messages_sent', 0)
        failed = summary.get('messages_failed', 0)
        if processed or sent or failed:
            self.stdout.write(
                f'Processed {processed} communications (sent={sent}, failed={failed}).'
            )
