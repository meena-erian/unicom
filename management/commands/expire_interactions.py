from django.core.management.base import BaseCommand
from unicom.services.interactions import expire_interactions


class Command(BaseCommand):
    help = 'Resolve expired user interactions. Run periodically (e.g. once per minute).'

    def handle(self, **options):
        expire_interactions()
