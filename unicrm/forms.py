from __future__ import annotations

from datetime import datetime
from typing import Iterable

import pytz
from django import forms
from django.utils import timezone

from unicom.models import Channel
from unicrm.models import Segment


class CommunicationComposeForm(forms.Form):
    segment = forms.ModelChoiceField(
        queryset=Segment.objects.none(),
        label='Recipient segment',
        help_text='Which contacts should receive this communication.'
    )
    channel = forms.ModelChoiceField(
        queryset=Channel.objects.none(),
        label='Channel',
        help_text='Channel used to deliver the emails.'
    )
    subject_template = forms.CharField(
        label='Subject',
        max_length=255,
        required=False,
        help_text='Optional Jinja2 subject template. Leave blank to use a generic fallback.'
    )
    content = forms.CharField(
        label='Email content',
        widget=forms.Textarea,
        required=False,
        help_text='Editable HTML body rendered for every contact.'
    )
    send_at = forms.CharField(required=False)
    timezone = forms.CharField(required=False)

    def __init__(
        self,
        *args,
        segment_queryset: Iterable[Segment] | None = None,
        channel_queryset: Iterable[Channel] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields['segment'].queryset = segment_queryset or Segment.objects.all()
        self.fields['channel'].queryset = channel_queryset or Channel.objects.filter(active=True)
        self.cleaned_schedule_utc = None
        self.cleaned_schedule_local = None

        if not self.is_bound:
            channel_qs = self.fields['channel'].queryset
            if channel_qs.count() == 1:
                default_channel = channel_qs.first()
                if default_channel:
                    self.initial['channel'] = str(default_channel.pk)
                    self.fields['channel'].initial = str(default_channel.pk)

    def clean_content(self) -> str:
        content = (self.cleaned_data.get('content') or '').strip()
        if not content:
            raise forms.ValidationError('Please provide the email content before sending.')
        return content

    def clean(self):
        cleaned = super().clean()
        send_at_raw = cleaned.get('send_at')
        timezone_name = (cleaned.get('timezone') or 'UTC').strip() or 'UTC'

        if send_at_raw:
            try:
                naive_dt = datetime.strptime(send_at_raw, '%Y-%m-%dT%H:%M')
            except ValueError:
                self.add_error('send_at', 'Invalid date/time format.')
                return cleaned

            try:
                tz = pytz.timezone(timezone_name)
            except pytz.exceptions.UnknownTimeZoneError:
                tz = pytz.UTC

            local_dt = tz.localize(naive_dt)
            # Store for access after validation
            self.cleaned_schedule_local = local_dt

            utc_dt = local_dt.astimezone(pytz.UTC)
            if utc_dt <= timezone.now():
                self.add_error('send_at', 'Please choose a future time or leave blank to send now.')
            else:
                self.cleaned_schedule_utc = utc_dt
        else:
            self.cleaned_schedule_utc = None
            self.cleaned_schedule_local = None

        return cleaned
