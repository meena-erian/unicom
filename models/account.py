from django.db import models
from .constants import channels


class Account(models.Model):
    id = models.CharField(max_length=500, primary_key=True)
    platform = models.CharField(max_length=100, choices=channels)
    is_bot = models.BooleanField(default=False)
    name = models.CharField(max_length=100, null=True, blank=True)
    # member = models.ForeignKey(
    #     'Member', on_delete=models.DO_NOTHING, null=True, blank=True)
    raw = models.JSONField()

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