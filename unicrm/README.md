# Unicrm Setup Guide

Unicrm provides CRM models, templates, and campaign tooling that can be dropped into any Django project. It depends on **django-unicom**, so make sure Unicom is installed and configured before proceeding.

At a glance you get:

- Models for `Company`, `Contact`, `MailingList`, `Subscription`, `Segment`, `TemplateVariable`, `Communication`, and `CommunicationMessage`.
- Django-admin integration with code editors (via Django Ace) for template variables and segments, plus live previews.
- A templating runtime that renders communications through a sandboxed Jinja2 environment (`unicrm.services.template_renderer`).
- Staff dashboards at `/unicrm/communications/` showing campaign status, per-contact delivery metadata, and draft regeneration actions.
- A template-variable API used by the TinyMCE integration to offer CRM placeholders.

## 1. Install

Install the apps into your environment (order matters: Unicom first, then Unicrm):

```bash
pip install django-unicom
pip install django-unicrm
```

## 2. Configure Django

Add the required apps to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # …
    "django_ace",  # Code editor for segments and template variables
    "unicom",      # Messaging primitives used by Unicrm
    "unicrm",      # CRM models and dashboards
]
```

If you use a custom user model, define `AUTH_USER_MODEL` before importing `unicrm`.

## 3. Include URLs

Expose Unicrm endpoints in your root `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # …
    path("unicrm/", include("unicrm.urls")),
]
```

This enables staff dashboards at `/unicrm/communications/` plus supporting APIs.

## 4. Run migrations

Apply the Unicrm migrations:

```bash
python manage.py migrate unicrm
```

The final migration fires a post-migrate hook that seeds default segments and ensures every auth user has a matching `Contact`.

## 5. Contact auto-sync

Unicrm wires its signals automatically—no extra registration needed. Behind the scenes:

- `post_save` on the active auth model maintains the corresponding `Contact`.
- `post_migrate` backfills both contacts and default segments.

To force a full resync manually:

```bash
python manage.py shell -c "from unicrm.services.user_contact_sync import sync_all_user_contacts; sync_all_user_contacts()"
```

## 6. Optional settings

| Setting | Purpose | Default |
| --- | --- | --- |
| `UNICRM_AUTO_START_SCHEDULER` | Auto-start the communication draft scheduler when ASGI workers launch. | `True` |
| `UNICRM_SCHEDULER_INTERVAL` | Poll interval (seconds) for draft regeneration. | `10` |

Shared settings inherited from Unicom (e.g., `DJANGO_PUBLIC_ORIGIN`, `UNICOM_TINYMCE_API_KEY`) should also be configured when applicable.

## 7. Scheduled communications command

Unicrm exposes a management command for generating drafts for scheduled communications:

```bash
# Run continuously (default 10-second interval)
python manage.py send_scheduled_communications

# Custom interval
python manage.py send_scheduled_communications --interval 30

# Single pass for debugging
python manage.py send_scheduled_communications --run-once -vv
```

Use this alongside your existing Unicom worker setup when you want Unicrm campaigns to deliver automatically.

## 8. Operating checklist

1. Populate Companies, Contacts, Mailing Lists, and Subscriptions via Django admin.
2. Define template variables under **Unicrm → Template variables** (default snippets live in `unicrm/templates/unicrm/snippets/`).
3. Create or adjust segments via the admin – code snippets are executed through a safe helper before each campaign.
4. Compose communications in the admin, select a channel, segment, template, optional subject, and schedule.
5. Trigger draft generation from the `/unicrm/communications/<id>/` dashboard or let the scheduled command handle it.
