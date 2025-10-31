THe current templating system allows us to save the email as is as a template, nothing defines which parts are fixed and which are
  to be populated with variables. That's useful in certain scenarios especially since we also implemented LLM function to populate
  templates as per user instructions. However, we need to extend this system without breaking backward compatibility and without
  breaking changes that forces us to refactor everything or break backward compatibility. This must be done in phases so we can test
  after each phase and ensure that everything is working find. First of all, for many scenarios, we don't necessarily need an LLM to
  populate the template. we just need to schedule the template to be sent to each of a thousand contact or so, with exact same
  content, only name or few other variables will varry. it would be very pointless and expensive to try to do that using LLM calls for
  each. And then in some other scenario, we might consider having the LLM choose which template is the most suitable for a specific
  lead and populate it by using it as a tool, where the LLM will only see the template as a tool, with a description outlining what it
  is to be used for and a list of fields with their description for the variables in the template, but other than that, the LLM
  doesn't have to worry about the whole code of the template, it only sees the variables and descriptions. Before we jump into
  implementation, we need to discuss a few aspects of how we can implement this, including what template processing tools to use and
  more. Althoug in many cases a template that simply allows inserting variables might be sufficient, especially if we can somehow make
  the list of available variables available in TinyMCE out-of-the-box so admins editing the template manually can easily drop them,
  but having some advanced templating features too would be nice, such as being able to conditionally render a section, or iterate
  over a template variable that is a list or so... but we don't want to over complicate things, we need to find a clean and
  straightforward approache that still somehow achieves most of this. What do you suggest? please provide multiple options while
  comparing each, and before you can suggest anything, you would have to study the existing system in order to make relevant
  suggestions

# Phase 1
I think it would be better if I help you by at least defining the phases. So, Phase 1: introducing cusomizable variables and contact
  data. Right now, when drafting an email, typically we can only specify the recipient, cc, bcc, date and time, eubject, etc.. We
  don't exactly have a data structure for mass-mailing/email-marketing. So, before we can get started with any of that, we need to
  first add an app, let's call it unicrm, and we need to define some models in it, we can start with a Contact model, related to a
  Company model, and has a json field for custom attributes, and a Segment model, containing a custom python function for filtartion
  of contacts, and a Communication model that is linked to a Segment and a template and a schedule possibly for a time in the furture
  and also keeps track of many unicom messages, and an aggregated summary of the status of these messages. But while defining these
  models keep in mind that in order to establish a one way dependecy where unicrm depends on unicom but unicom isn't even aware of
  unicrm, you must not make any modifications to unicom models, and finally, each contact can have one or more Subscription instances
  to one or more MailingList where the Subscription model also has fields such as the timestamp they unsubscribed and the feedback
  they provided, which are null initially, and now with all of these models, there's a lot of data related to each Contact which can
  be used as variables in a mailing, but no specific description for any or specific code for extracting it. That's why we might have
  to define a TemplateVariable model which can carry an arbitraty python function which takes the contact object as input and extracts
  something out of it, and of course has a clear description field of what field of information is extracts exactly, and then we will
  need an API that returns a list of these variables which will be part of the TinyMCE template editor so we can easily insert
  placeholders which will be replaced with what the TemplateVariable returns.

# Phase 2 – Jinja2 templating
- Message templates render through a sandboxed Jinja2 environment so emails can conditionally include sections and iterate over lists without invoking the LLM.
- The template context exposes:
  - `contact`: Sanitised contact data (`contact.first_name`, `contact.company.name`, `contact.attributes`, `contact.subscriptions`, etc.).
  - `company`: Shortcut to the contact’s company dictionary.
  - `variables`: All active `TemplateVariable` outputs (e.g. `variables.contact_full_name`).
  - `communication`: Optional campaign metadata when rendering inside a Communication.
  - `now()`: Helper that returns the current time.
- TinyMCE now includes a **Variables** menu (fed by `/unicrm/api/template-variables/`) so editors can insert `{{ variables.<key> }}` snippets without leaving the WYSIWYG view.
- Jinja blocks are protected from TinyMCE cleanup (`{{ ... }}`, `{% ... %}`, `{# ... #}`), allowing advanced users to switch to the Code view for manual edits.
- Rendering falls back to the original HTML and surfaces errors if a placeholder is missing, making it obvious when additional context is required.
