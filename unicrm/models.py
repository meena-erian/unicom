from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from django.contrib.auth import get_user_model
from django.core.validators import validate_slug
from django.db import models
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


SNIPPETS_DIR = Path(__file__).resolve().parent / 'templates' / 'unicrm' / 'snippets'

SAFE_BUILTINS = {
    'str': str,
    'int': int,
    'float': float,
    'len': len,
    'min': min,
    'max': max,
    'sum': sum,
    'sorted': sorted,
    'round': round,
    'any': any,
    'all': all,
}


def _read_snippet(filename: str) -> str:
    path = SNIPPETS_DIR / filename
    try:
        return path.read_text(encoding='utf-8').strip() + '\n'
    except FileNotFoundError:
        return ''


def _default_template_variable_code() -> str:
    return _read_snippet('template_variable.py')


def _default_segment_code() -> str:
    return _read_snippet('segment_filter.py')


def compile_callable(code: str, func_name: str, extra_globals: dict[str, object] | None = None) -> Callable:
    """
    Compiles the provided code and returns the function with name ``func_name``.
    Allows full Python execution for staff users.
    """
    namespace: dict[str, object] = {}
    globals_dict: dict[str, object] = {'__builtins__': __builtins__}
    if extra_globals:
        globals_dict.update(extra_globals)
    exec(code, globals_dict, namespace)
    func = namespace.get(func_name)
    if not callable(func):
        raise ValueError(f"Callable `{func_name}` not found in provided code.")
    return func  # type: ignore[return-value]


class TimeStamped(models.Model):
    created_at = models.DateTimeField(_('Created at'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Updated at'), auto_now=True)

    class Meta:
        abstract = True


class Company(TimeStamped):
    """Represents an organisation that owns one or more contacts."""

    name = models.CharField(_('Name'), max_length=255)
    domain = models.CharField(
        _('Email domain'),
        max_length=255,
        blank=True,
        help_text=_('Primary email domain for this company (optional)')
    )
    website = models.URLField(_('Website'), blank=True)
    notes = models.TextField(_('Internal notes'), blank=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = _('Companies')

    def __str__(self) -> str:
        return self.name


class Contact(TimeStamped):
    """
    Stores CRM contact information and custom attributes for template variables.
    """

    first_name = models.CharField(_('First name'), max_length=150, blank=True)
    last_name = models.CharField(_('Last name'), max_length=150, blank=True)
    email = models.EmailField(_('Email'), unique=True)
    phone_number = models.CharField(_('Phone number'), max_length=50, blank=True)
    job_title = models.CharField(_('Job title'), max_length=150, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contacts',
    )
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='owned_contacts',
        help_text=_('Optional staff owner responsible for this contact.')
    )
    attributes = models.JSONField(
        _('Custom attributes'),
        default=dict,
        blank=True,
        help_text=_('Arbitrary data map available to template variables.')
    )

    class Meta:
        ordering = ('last_name', 'first_name')

    def __str__(self) -> str:
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email


class MailingList(TimeStamped):
    """Named mailing lists that contacts can subscribe to."""

    name = models.CharField(_('Name'), max_length=255, unique=True)
    slug = models.SlugField(
        _('Slug'),
        max_length=255,
        unique=True,
        validators=[validate_slug],
        help_text=_('URL-friendly identifier for public subscription management.')
    )
    description = models.TextField(_('Description'), blank=True)

    class Meta:
        ordering = ('name',)

    def __str__(self) -> str:
        return self.name


class Subscription(TimeStamped):
    """
    Links a contact to a mailing list and tracks subscription state.
    """

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='subscriptions')
    mailing_list = models.ForeignKey(MailingList, on_delete=models.CASCADE, related_name='subscriptions')
    subscribed_at = models.DateTimeField(_('Subscribed at'), auto_now_add=True)
    unsubscribed_at = models.DateTimeField(_('Unsubscribed at'), null=True, blank=True)
    unsubscribe_feedback = models.TextField(_('Unsubscribe feedback'), blank=True)

    class Meta:
        unique_together = ('contact', 'mailing_list')
        ordering = ('-subscribed_at',)

    def __str__(self) -> str:
        return f"{self.contact} -> {self.mailing_list}"

    @property
    def is_active(self) -> bool:
        return self.unsubscribed_at is None

    def mark_unsubscribed(self, feedback: str | None = None) -> None:
        """
        Convenience helper to record an unsubscribe event with optional feedback.
        """
        self.unsubscribed_at = timezone.now()
        if feedback:
            self.unsubscribe_feedback = feedback
        self.save(update_fields=['unsubscribed_at', 'unsubscribe_feedback', 'updated_at'])


class Segment(TimeStamped):
    """
    Defines a dynamic collection of contacts via a stored Python snippet.
    The snippet must declare a function named `apply` that accepts a QuerySet.
    """

    name = models.CharField(_('Name'), max_length=255, unique=True)
    description = models.TextField(_('Description'), blank=True)
    code = models.TextField(
        _('Filter code'),
        default=_default_segment_code,
        help_text=_(
            'Python snippet with a function `apply(qs)` returning a filtered QuerySet. '
            'The `qs` argument contains `unicrm.Contact` records.'
        )
    )

    class Meta:
        ordering = ('name',)

    def __str__(self) -> str:
        try:
            qs = self.apply()
            count = qs.count()
            return f"{self.name} ({count} contacts)"
        except Exception as exc:  # pragma: no cover - defensive
            return f"{self.name} [error: {exc}]"

    def get_callable(self) -> Callable[[QuerySet], QuerySet]:
        """
        Returns the compiled `apply` function for this segment.
        """
        if not hasattr(self, '_compiled_callable'):
            extras = {
                'timezone': timezone,
                'Contact': Contact,
                'Company': Company,
                'QuerySet': QuerySet,
            }
            self._compiled_callable = compile_callable(self.code, 'apply', extras)
        return self._compiled_callable  # type: ignore[attr-defined]

    def apply(self, qs: QuerySet | None = None) -> QuerySet:
        """
        Applies the stored filter function to the provided QuerySet (or all contacts).
        """
        base_qs = qs or Contact.objects.all()
        return self.get_callable()(base_qs)

    def sample_contacts(self, limit: int = 10) -> Sequence[Contact]:
        """
        Returns a limited list of contacts belonging to this segment for previews.
        """
        try:
            return list(self.apply().select_related('company').order_by('pk')[:limit])
        except Exception:
            return []


class TemplateVariable(TimeStamped):
    """
    Describes a template placeholder and how to compute its value for a contact.
    """

    key = models.CharField(
        _('Key'),
        max_length=100,
        unique=True,
        help_text=_('Slug-like identifier used in templates, e.g. "contact_first_name".')
    )
    label = models.CharField(
        _('Label'),
        max_length=255,
        help_text=_('Human-readable label for editors.')
    )
    description = models.TextField(
        _('Description'),
        help_text=_('Explain exactly what data this variable returns.')
    )
    code = models.TextField(
        _('Code'),
        default=_default_template_variable_code,
        help_text=_(
            'Python snippet defining `compute(contact)` which returns a string value.'
        )
    )
    is_active = models.BooleanField(_('Is active'), default=True)

    class Meta:
        ordering = ('key',)

    def __str__(self) -> str:
        values = self.sample_values(limit=3)
        preview = ', '.join(values) if values else 'no sample'
        return f"{self.label} [{self.key}] -> {preview}"

    def get_callable(self) -> Callable[[Contact], object]:
        """
        Compiles and returns the `compute` function described by this variable.
        """
        if not hasattr(self, '_compiled_callable'):
            extras = {
                'timezone': timezone,
                'Contact': Contact,
                'Company': Company,
            }
            self._compiled_callable = compile_callable(self.code, 'compute', extras)
        return self._compiled_callable  # type: ignore[attr-defined]

    def sample_values(self, limit: int = 3) -> list[str]:
        """
        Returns preview values for the first few contacts to aid editors.
        """
        contacts = Contact.objects.order_by('pk')[:limit]
        values: list[str] = []
        func = None
        try:
            func = self.get_callable()
        except Exception as exc:  # pragma: no cover - defensive
            return [f"<error: {exc}>"]
        for contact in contacts:
            try:
                value = func(contact)
            except Exception as exc:  # pragma: no cover - defensive
                value = f"<error: {exc}>"
            values.append(str(value))
        return values


class Communication(TimeStamped):
    """
    Represents a planned outreach effort using rich HTML content and a segment of contacts.
    """

    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('scheduled', _('Scheduled')),
        ('sending', _('Sending')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]

    segment = models.ForeignKey(Segment, on_delete=models.PROTECT, related_name='communications')
    channel = models.ForeignKey(
        'unicom.Channel',
        on_delete=models.PROTECT,
        related_name='unicrm_communications',
        verbose_name=_('Channel'),
        help_text=_('Channel used to send this communication.'),
        null=True,
        blank=True,
    )
    initiated_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_communications'
    )
    scheduled_for = models.DateTimeField(_('Scheduled for'), null=True, blank=True)
    subject_template = models.CharField(
        _('Subject template'),
        max_length=255,
        blank=True,
        help_text=_('Optional Jinja2 template used for the email subject line.')
    )
    content = models.TextField(
        _('Content'),
        blank=True,
        help_text=_('HTML content customised specifically for this communication.')
    )
    status = models.CharField(_('Status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    status_summary = models.JSONField(
        _('Status summary'),
        default=dict,
        blank=True,
        help_text=_('Aggregated counters for linked messages (e.g. sent, delivered, failed).')
    )

    class Meta:
        ordering = ('-created_at',)

    def __str__(self) -> str:
        title = self.display_title
        return f"{title} ({self.segment.name})"

    def get_renderable_content(self) -> str:
        """
        Returns the HTML content that should be rendered for this communication.
        """
        return self.content or ''

    @property
    def display_title(self) -> str:
        if self.subject_template:
            return self.subject_template
        if self.content:
            text = self.content.strip()
            return text[:60] + ('…' if len(text) > 60 else '')
        return f"Communication {self.pk or ''}".strip()

    def refresh_status_summary(self, commit: bool = True) -> dict[str, int]:
        """
        Aggregates delivery metrics and updates the communication status.
        """
        from django.db.models import Q

        deliveries = self.messages.select_related('message')
        total = deliveries.count()
        scheduled = 0
        failed = 0
        sent = 0
        delivered = 0
        opened = 0
        clicked = 0

        for delivery in deliveries:
            metadata = delivery.metadata or {}
            status = metadata.get('status')
            if not status:
                status = 'sent' if delivery.message_id else 'pending'

            if status == 'failed':
                failed += 1
            elif status == 'sent':
                sent += 1
            else:
                scheduled += 1

            message = delivery.message
            if message:
                if getattr(message, 'delivered', False):
                    delivered += 1
                if getattr(message, 'opened', False) or getattr(message, 'seen', False):
                    opened += 1
                if getattr(message, 'link_clicked', False) or getattr(message, 'clicked_links', None):
                    if getattr(message, 'clicked_links', []):
                        clicked += 1

        totals = {
            'total': total,
            'scheduled': scheduled,
            'failed': failed,
            'sent': sent,
            'delivered': delivered,
            'opened': opened,
            'clicked': clicked,
        }
        totals['pending'] = max(total - (sent + failed), 0)

        new_status = self.status
        if self.status != 'cancelled':
            if totals['total'] == 0:
                new_status = 'draft'
            elif totals['scheduled'] > 0:
                new_status = 'scheduled'
            elif totals['pending'] > 0:
                new_status = 'sending'
            else:
                new_status = 'completed'

        updates = {}
        if self.status_summary != totals:
            self.status_summary = totals
            updates['status_summary'] = totals
        if new_status != self.status:
            self.status = new_status
            updates['status'] = new_status

        if updates and commit:
            self.save(update_fields=list(updates.keys()) + ['updated_at'])

        return totals


class CommunicationMessage(TimeStamped):
    """
    Associates a unicom Message with a communication and contact for aggregation.
    """

    communication = models.ForeignKey(
        Communication,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='communications'
    )
    draft = models.ForeignKey(
        'unicom.DraftMessage',
        on_delete=models.CASCADE,
        related_name='unicrm_links',
        null=True,
        blank=True
    )
    message = models.ForeignKey(
        'unicom.Message',
        on_delete=models.CASCADE,
        related_name='unicrm_links',
        null=True,
        blank=True
    )
    metadata = models.JSONField(_('Metadata'), default=dict, blank=True)

    class Meta:
        unique_together = ('communication', 'contact')
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.communication} -> {self.contact}"

    def message_status(self) -> str:
        """
        Derives a coarse status based on draft and message state.
        """
        metadata_status = (self.metadata or {}).get('status')
        if metadata_status:
            return metadata_status

        msg = self.message
        if not msg:
            return 'pending'
        if getattr(msg, 'seen', False) or getattr(msg, 'opened', False):
            return 'seen'
        if getattr(msg, 'delivered', False):
            return 'delivered'
        if getattr(msg, 'sent', False):
            return 'sent'
        return 'pending'
