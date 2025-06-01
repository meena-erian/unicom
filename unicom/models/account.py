from django.db import models
from .constants import channels


class Account(models.Model):
    id = models.CharField(max_length=500, primary_key=True)
    channel = models.ForeignKey('unicom.Channel', on_delete=models.CASCADE)
    platform = models.CharField(max_length=100, choices=channels)
    is_bot = models.BooleanField(default=False)
    name = models.CharField(max_length=100, null=True, blank=True)
    blocked = models.BooleanField(default=False, help_text="Whether this account is blocked from sending messages")
    member = models.ForeignKey(
        'unicom.Member', on_delete=models.SET_NULL, null=True, blank=True, related_name='accounts',
        help_text="Associated CRM member if matched"
    )
    default_category = models.ForeignKey(
        'unicom.RequestCategory',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Default category for messages from this account"
    )
    raw = models.JSONField(default=dict)

    def __str__(self) -> str:
        return f"{self.platform}:{self.id} ({self.name})"

    # def get_menu(self):
    #     from robopower.models import Function
    #     # If self has a member, get the associated functions
    #     if self.member:
    #         member_functions = self.member.functions.all()
    #     else:
    #         member_functions = Function.objects.none()  # This returns an empty QuerySet

    #     # Get the public functions
    #     public_functions = Function.objects.filter(public=True)

    #     # Combine the two querysets
    #     combined_functions = member_functions | public_functions

    #     # Get unique function names and return
    #     return list(set(map(lambda f: f.name, combined_functions)))