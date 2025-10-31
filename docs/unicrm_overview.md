# Unicrm Overview

## What’s Included
- **Data model** (app `unicrm`):
  - `Company`, `Contact`, `MailingList`, `Subscription`, `Segment`, `TemplateVariable`, `Communication`, `CommunicationMessage`.
  - `Segment` and `TemplateVariable` store Python snippets, compiled in a sandboxed helper so admins can define dynamic contact slices and reusable variables.
  - All models inherit a shared timestamp mixin and appear in Django admin with previews, code editors (via Django Ace), and sample data.

- **Templating & scheduling runtime**:
  - Emails render with a sandboxed Jinja2 environment (`unicrm.services.template_renderer`).
  - Context exposes `contact`, `company`, `variables`, `communication`, and a `now()` helper.
  - Errors fall back to the original HTML and are reported for diagnostics.
  - Campaign orchestration (`unicrm.services.communication_scheduler.generate_drafts_for_communication`) materialises drafts for each contact, ready for the existing scheduler.

- **Editor integration**:
  - TinyMCE now protects Jinja tokens and adds a **Variables** menu populated from `/unicrm/api/template-variables/`, inserting snippets like `{{ variables.contact_full_name }}`.
  - Template variable API returns labels, descriptions, placeholders, and sample outputs to guide authors and LLM tools.

- **Marketing dashboards**:
  - Staff-only pages at `/unicrm/communications/` list communications, show live status summaries (scheduled, sent, delivered, opened, clicked, failed), and allow regenerating drafts.
  - Communication detail pages surface per-contact delivery metadata, linked draft/message IDs, and templating errors.

- **Tests & dependencies**:
  - Unit tests cover template rendering and communication scheduling (`unicrm/tests/test_template_renderer.py`, `unicrm/tests/test_communication_scheduler.py`).
  - Requirements include `Jinja2>=3.1.4,<4.0` to support rendering.

## How to Use
1. **Manage CRM data**: populate Companies, Contacts, Mailing Lists, and Subscriptions via the Django admin.
2. **Define variables**: create `TemplateVariable` entries; code editor defaults to the snippet stored under `unicrm/templates/unicrm/snippets/`.
3. **Build segments**: author filtering logic in `Segment.code` to target contacts for campaigns; previews show counts and sample contacts.
4. **Create communications**: in the Django admin, add a `Communication` (via *Unicrm → Communications*) selecting the email `Channel`, target `Segment`, template, optional subject Jinja, and schedule.
5. **Prepare campaigns**: from the staff dashboard visit `/unicrm/communications/<id>/`, click “Generate/Refresh Drafts” to materialise per-contact drafts, then let the existing scheduler send them at the chosen time.

## Status & Next Steps
### Completed
- CRM schema and admin UX.
- Jinja2 renderer with safe context shaping and placeholder error reporting.
- TinyMCE variable picker, Jinja token preservation, and staff dashboards for campaign orchestration.
- Template-variable API, draft generation service, and supporting unit tests.

### Upcoming Work
- Extend Segment/TemplateVariable execution sandboxing or linting as needed.
- Document best practices for writing snippets and add guardrails/approvals for risky code.
- Enhance TinyMCE with snippet libraries for common Jinja loops/conditionals.
- Add end-to-end tests for actual message sends and integrate with LLM tooling in later phases.
