from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from unicrm.models import Communication
from unicrm.services.communication_scheduler import generate_drafts_for_communication


def staff_required():
    return user_passes_test(lambda u: u.is_staff, login_url='admin:login')


@method_decorator(staff_required(), name='dispatch')
class CommunicationListView(View):
    template_name = 'unicrm/communications/list.html'

    def get(self, request, *args, **kwargs):
        communications = (
            Communication.objects
            .select_related('template', 'segment', 'channel', 'initiated_by')
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
            Communication.objects.select_related('template', 'segment', 'channel', 'initiated_by'),
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
