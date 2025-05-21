from django.db import models
from .constants import channels


class Update(models.Model):
    bot = models.ForeignKey('unicom.Bot', on_delete=models.CASCADE)
    platform = models.CharField(max_length=100, choices=channels)
    id = models.CharField(max_length=100, primary_key=True)
    payload = models.JSONField()
    message = models.ForeignKey('unicom.Message', null=True, blank=True, on_delete=models.DO_NOTHING)

    def __str__(self) -> str:
        if self.message:
            return f"{self.id}->Message:{self.message}"
        return super().__str__()