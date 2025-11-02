from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from unicrm.forms import CommunicationComposeForm
from unicrm.models import Communication, Segment
from unicrm.services.communication_scheduler import generate_drafts_for_communication
from unicom.models import Channel


def staff_required():
    return user_passes_test(lambda u: u.is_staff, login_url='admin:login')


@method_decorator(staff_required(), name='dispatch')
class CommunicationListView(View):
    template_name = 'unicrm/communications/list.html'

    def get(self, request, *args, **kwargs):
        communications = (
            Communication.objects
            .select_related('segment', 'channel', 'initiated_by')
            .order_by('-created_at')
        )
        for communication in communications:
            communication.refresh_status_summary(commit=False)
        return render(request, self.template_name, {'communications': communications})


@method_decorator(staff_required(), name='dispatch')
class CommunicationDetailView(View):
    template_name = 'unicrm/communications/detail.html'

    def get(self, request, pk, *args, **kwargs):
        communication = get_object_or_404(
            Communication.objects.select_related('segment', 'channel', 'initiated_by'),
            pk=pk,
        )
        communication.refresh_status_summary(commit=False)
        deliveries = (
            communication.messages
            .select_related('contact', 'draft', 'message')
            .order_by('contact__email')
        )
        return render(
            request,
            self.template_name,
            {
                'communication': communication,
                'deliveries': deliveries,
            }
        )

    def post(self, request, pk, *args, **kwargs):
        communication = get_object_or_404(Communication, pk=pk)
        result = generate_drafts_for_communication(communication)
        messages.success(
            request,
            f"Prepared communication for {result.communication.segment.name}: "
            f"{result.created} drafts created, {result.updated} updated, {result.skipped} skipped."
        )
        if result.errors:
            for err in result.errors:
                messages.warning(request, f"Template issue: {err}")
        return redirect(reverse('unicrm:communications-detail', args=[communication.pk]))


@method_decorator(staff_required(), name='dispatch')
class CommunicationComposeView(View):
    template_name = 'unicrm/communications/compose.html'

    def get_form(self, request, data=None):
        return CommunicationComposeForm(
            data,
            segment_queryset=Segment.objects.order_by('name'),
            channel_queryset=Channel.objects.filter(active=True, platform='Email').order_by('name'),
        )

    def get(self, request, *args, **kwargs):
        form = self.get_form(request)
        return render(request, self.template_name, self._context(request, form))

    def post(self, request, *args, **kwargs):
        form = self.get_form(request, request.POST)
        if form.is_valid():
            scheduled_at = form.cleaned_schedule_utc or timezone.now()

            communication = Communication.objects.create(
                segment=form.cleaned_data['segment'],
                channel=form.cleaned_data['channel'],
                initiated_by=request.user if request.user.is_authenticated else None,
                scheduled_for=scheduled_at,
                subject_template=form.cleaned_data['subject_template'] or '',
                content=form.cleaned_data['content'],
            )
            try:
                result = generate_drafts_for_communication(communication)
            except Exception as exc:
                communication.delete()
                messages.error(request, f'Failed to prepare communication: {exc}')
                return render(request, self.template_name, self._context(request, form))

            local_dt = form.cleaned_schedule_local
            if local_dt:
                display_time = local_dt
                messages.success(
                    request,
                    f'Communication scheduled for {display_time.strftime("%Y-%m-%d %H:%M %Z")}. '
                    f'{result.created} drafts created, {result.updated} updated, {result.skipped} skipped.'
                )
            else:
                messages.success(
                    request,
                    f'Communication queued to send immediately. '
                    f'{result.created} drafts created, {result.updated} updated, {result.skipped} skipped.'
                )
            if result.errors:
                for err in result.errors:
                    messages.warning(request, f'Template rendering issue: {err}')
            return redirect(reverse('unicrm:communications-detail', args=[communication.pk]))
        return render(request, self.template_name, self._context(request, form))

    def _context(self, request, form):
        segments = list(form.fields['segment'].queryset)
        segment_counts = {}
        for segment in segments:
            try:
                segment_counts[segment.pk] = segment.apply().count()
            except Exception:
                segment_counts[segment.pk] = 0
        channels = form.fields['channel'].queryset
        selected_channel = ''
        if 'channel' in form.fields:
            selected_channel = form['channel'].value()
            if not selected_channel:
                initial_channel = form.fields['channel'].initial or form.initial.get('channel')
                if initial_channel:
                    selected_channel = str(initial_channel)
        return {
            'form': form,
            'segments': segments,
            'segment_counts': segment_counts,
            'channels': channels,
            'selected_channel': selected_channel,
            'tinymce_api_key': getattr(settings, 'UNICOM_TINYMCE_API_KEY', None),
        }
