from django.db import models
from .constants import channels
from django.core.exceptions import ValidationError
from unicom.services.telegram.set_telegram_webhook import set_telegram_webhook
from unicom.services.email.validate_email_config import validate_email_config


class Bot(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100)
    platform = models.CharField(max_length=100, choices=channels)
    config = models.JSONField()

    active = models.BooleanField(default=False, editable=False)
    confirmed_webhook_url = models.CharField(max_length=500, null=True, blank=True, editable=False) # Used for Telegram and WhatsApp to check if the URL changed and update the service provided if it did
    error = models.CharField(max_length=500, null=True, blank=True, editable=False) # Used for Telegram and WhatsApp to check if the URL changed and update the service provided if it did

    def validate_SMTP_and_IMAP(self) -> bool:
        """
        Normalize and validate email client settings. Updates self.config, sets error/active flags.
        """
        try:
            normalized = validate_email_config(self.config or {})
            # Update config with normalized settings
            self.config = normalized
            self.error = None
            self.active = True
            return True
        except ValidationError as e:
            self.error = str(e)
            self.active = False
            return False

    def validate(self):
        print(f"Validating {self.name} ({self.platform})")
        attributes_monitored_for_change = ('active', 'error', 'confirmed_webhook_url', 'config')
        # Snapshot old values for comparison
        old = type(self).objects.filter(pk=self.pk).values(
            *attributes_monitored_for_change
        ).first() or {}

        # Reset status
        self.confirmed_webhook_url = None
        self.active = False

        if self.platform == 'Telegram':
            try:
                result = set_telegram_webhook(self)
                if not result.get('ok'):
                    self.error = result.get('description', 'Could not update webhook URL')
                else:
                    self.active = True
                    self.error = None
            except Exception as e:
                self.error = f"Failed to set Telegram webhook: {str(e)}"

        elif self.platform == 'WhatsApp':
            return True

        elif self.platform == 'Email':
            self.validate_SMTP_and_IMAP()

        # Determine changed fields and update via QuerySet.update() to avoid signals
        changes = {}
        for field in attributes_monitored_for_change:
            old_value = old.get(field)
            new_value = getattr(self, field)
            if old_value != new_value:
                changes[field] = new_value

        if changes:
            print(f"Changes detected for {self.name} ({self.platform}): {changes}")
            type(self).objects.filter(pk=self.pk).update(**changes)
        else:
            print(f"No changes detected for {self.name} ({self.platform})")

        print(f"Webhook URL: {self.confirmed_webhook_url}")
        print(f"Active: {self.active}")
        print(f"Error: {self.error}")
        return self.active

    def __str__(self):
        status_emoji = "✅" if self.active else ( "❌" if self.error is not None else "⚪️" )
        if self.error:
            status_emoji = "⚠️"
        return f"{status_emoji} {self.name} ({self.platform})" if self.error is None else f"{status_emoji} {self.name} ({self.platform}) - {self.error}"

