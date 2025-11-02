from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, Mapping
import re
from urllib.parse import unquote

from django.utils import timezone
from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment

from unicrm.models import Communication, Company, Contact, TemplateVariable


PROTECTED_PLACEHOLDER_RE = re.compile(r'<!--\s*mce:protected\s+([^>]+?)-->')


def _datetime_format(value, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
    if not value:
        return ""
    if timezone.is_naive(value):  # pragma: no cover - defensive branch
        value = timezone.make_aware(value)
    return timezone.localtime(value).strftime(fmt)


@lru_cache(maxsize=1)
def get_jinja_environment() -> SandboxedEnvironment:
    """
    Returns a singleton sandboxed environment for rendering email templates.
    """
    env = SandboxedEnvironment(
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    env.filters['datetime'] = _datetime_format
    env.globals.update({
        'now': timezone.now,
    })
    return env


def unprotect_tinymce_markup(content: str | None) -> str:
    """Restore TinyMCE protected placeholders ({{ ... }}) back to plain Jinja markup."""
    if not content:
        return content or ''

    def _restore(match: re.Match[str]) -> str:
        encoded = match.group(1).strip()
        try:
            return unquote(encoded)
        except Exception:  # pragma: no cover - defensive
            return encoded

    return PROTECTED_PLACEHOLDER_RE.sub(_restore, content)


def build_company_context(company: Company | None) -> Dict[str, Any]:
    if not company:
        return {}
    return {
        'id': company.pk,
        'name': company.name,
        'domain': company.domain,
        'website': company.website,
        'notes': company.notes,
        'created_at': company.created_at,
        'updated_at': company.updated_at,
    }


def build_subscription_context(contact: Contact) -> Iterable[Dict[str, Any]]:
    for subscription in contact.subscriptions.select_related('mailing_list'):
        yield {
            'mailing_list': {
                'id': subscription.mailing_list.pk,
                'name': subscription.mailing_list.name,
                'slug': subscription.mailing_list.slug,
                'description': subscription.mailing_list.description,
            },
            'is_active': subscription.is_active,
            'subscribed_at': subscription.subscribed_at,
            'unsubscribed_at': subscription.unsubscribed_at,
            'unsubscribe_feedback': subscription.unsubscribe_feedback,
        }


def build_contact_context(contact: Contact) -> Dict[str, Any]:
    """
    Converts a Contact model into a serialisable structure that is safe to expose to templates.
    """
    return {
        'id': contact.pk,
        'first_name': contact.first_name,
        'last_name': contact.last_name,
        'email': contact.email,
        'phone_number': contact.phone_number,
        'job_title': contact.job_title,
        'created_at': contact.created_at,
        'updated_at': contact.updated_at,
        'attributes': contact.attributes or {},
        'company': build_company_context(contact.company),
        'subscriptions': list(build_subscription_context(contact)),
    }


def build_variables_context(contact: Contact) -> Dict[str, Any]:
    """
    Evaluates all active TemplateVariables for the given contact.
    """
    results: Dict[str, Any] = {}
    for variable in TemplateVariable.objects.filter(is_active=True):
        try:
            results[variable.key] = variable.get_callable()(contact)
        except Exception as exc:  # pragma: no cover - defensive
            results[variable.key] = f"<error: {exc}>"
    return results


@dataclass
class RenderResult:
    html: str
    context: Dict[str, Any]
    variables: Dict[str, Any]
    errors: list[str]


def render_template_for_contact(
    template_html: str,
    *,
    contact: Contact,
    communication: Communication | None = None,
    extra_context: Mapping[str, Any] | None = None,
) -> RenderResult:
    """
    Renders the provided HTML using the sandboxed Jinja2 environment.
    """
    env = get_jinja_environment()
    rendered_context: Dict[str, Any] = {
        'contact': build_contact_context(contact),
        'company': build_company_context(contact.company),
        'variables': build_variables_context(contact),
        'communication': None,
    }

    if communication:
        rendered_context['communication'] = {
            'id': communication.pk,
            'name': str(communication),
            'status': communication.status,
            'scheduled_for': communication.scheduled_for,
            'status_summary': communication.status_summary,
        }

    if extra_context:
        rendered_context.update(extra_context)

    template_html = unprotect_tinymce_markup(template_html)
    template = env.from_string(template_html)
    errors: list[str] = []
    try:
        html = template.render(rendered_context)
    except TemplateError as exc:
        errors.append(str(exc))
        html = template_html
    return RenderResult(
        html=html,
        context=rendered_context,
        variables=rendered_context['variables'],
        errors=errors,
    )
