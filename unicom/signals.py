from unicom.models import Message, AccountChat, Bot
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.db import transaction
from django.dispatch import receiver
import threading


def handle_new_message(message):
    sender = message.sender
    # chat = message.chat
    # account_chat = AccountChat.objects.get(chat=chat, account=sender)
    print(f"New Message Received: {sender.name}: {message.text}")


@receiver(post_save, sender=Message)
def run_message_after_insert(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(lambda: threading.Thread(target=handle_new_message, args=(instance,)).start())


@receiver(pre_save, sender=Bot)
def bot_pre_save(sender, instance, **kwargs):
    # Save old config for comparison in post_save
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_config = old.config
        except sender.DoesNotExist:
            instance._old_config = None


@receiver(post_save, sender=Bot)
def run_bot_after_insert(sender, instance, created, **kwargs):
    # Check if created or config changed
    config_changed = not created and getattr(instance, '_old_config', None) != instance.config
    if created or config_changed:
        transaction.on_commit(lambda: threading.Thread(target=instance.validate).start())
 