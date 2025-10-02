from django.db import models
from django.utils import timezone


class CallbackExecution(models.Model):
    """
    Tracks callback button executions to ensure each callback is processed exactly once
    across multiple Django processes, with built-in security validation.
    """
    callback_id = models.CharField(max_length=100, unique=True, db_index=True,
                                   help_text="Telegram's unique callback query ID")
    callback_message = models.ForeignKey('unicom.Message', on_delete=models.CASCADE,
                                         related_name='callback_executions')
    original_message = models.ForeignKey('unicom.Message', on_delete=models.CASCADE,
                                         related_name='button_callbacks',
                                         help_text="The message containing the buttons")
    callback_data = models.CharField(max_length=500, help_text="Button callback data")
    authorized_user = models.ForeignKey('unicom.Account', on_delete=models.CASCADE,
                                        help_text="Only this user can trigger this callback")
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'unicom_callback_execution'
        verbose_name = 'Callback Execution'
        verbose_name_plural = 'Callback Executions'

    def mark_processed(self):
        """Mark this callback as processed to prevent re-execution"""
        self.processed_at = timezone.now()
        self.save(update_fields=['processed_at'])

    def is_processed(self):
        """Check if this callback has already been processed"""
        return self.processed_at is not None

    def __str__(self):
        status = "✅ Processed" if self.is_processed() else "⏳ Pending"
        return f"{status} - {self.callback_data} by {self.authorized_user.username}"