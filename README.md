# Django Unicom

**Unified communication layer for Django** — easily integrate Telegram bots, WhatsApp bots, and Email bots with a consistent API across all platforms.

---

## 🚀 Quick Start

1. **Install the package:**
   ```bash
   pip install django-unicom
   ```

2. **Add required apps to your Django settings:**

   ```python
   INSTALLED_APPS = [
       ...
       'django_ace',  # Required for the JSON configuration editor
       'unicom',
   ]
   ```

3. **Include `unicom` URLs in your project's `urls.py`:**

   > This is required so that webhook URLs can be constructed correctly.

   ```python
   from django.urls import path, include

   urlpatterns = [
       ...
       path('unicom/', include('unicom.urls')),
   ]
   ```

4. **Define your public origin:**
   In your Django `settings.py`:

   ```python
   DJANGO_PUBLIC_ORIGIN = "https://yourdomain.com"
   ```

   Or via environment variable:

   ```env
   DJANGO_PUBLIC_ORIGIN=https://yourdomain.com
   ```

5. *(Optional, but recommended)* **Set your TinyMCE Cloud API key** — required if you plan to compose **Email** messages from the Django admin UI.

   Obtain a free key at <https://www.tiny.cloud>, then add it to your `settings.py`:

   ```python
   UNICOM_TINYMCE_API_KEY = "your-tinymce-api-key"
   ```

   Or via environment variable:

   ```env
   UNICOM_TINYMCE_API_KEY=your-tinymce-api-key
   ```

   and then you would still have to load it in settings.py

   ```python
   UNICOM_TINYMCE_API_KEY = os.getenv('UNICOM_TINYMCE_API_KEY', '')
   ```

6. *(Optional)* **Set your OpenAI API key** — required if you plan to use the AI-powered template population service.

   Obtain a key from <https://platform.openai.com/api-keys>, then set it as an environment variable:

   ```env
   OPENAI_API_KEY="your-openai-api-key"
   ```

   The application will automatically pick it up from the environment.

That's it! Unicom can now register and manage public-facing webhooks (e.g., for Telegram bots) based on your defined base URL and can automatically sync with email clients.

## 📝 Features & Usage

### Channel Configuration

Each communication channel (Email, Telegram, WhatsApp) requires minimal configuration:

#### Email Channel
```python
# Basic configuration - SMTP/IMAP settings are auto-discovered
email_config = {
    "EMAIL_ADDRESS": "your-email@example.com",
    "EMAIL_PASSWORD": "your-password"
}

# Optional: Override auto-discovered settings if needed
email_config_with_custom_settings = {
    "EMAIL_ADDRESS": "your-email@example.com",
    "EMAIL_PASSWORD": "your-password",
    "IMAP": {  # Optional - will be auto-discovered if not provided
        "host": "imap.example.com",
        "port": 993,
        "use_ssl": True,
        "protocol": "IMAP"
    },
    "SMTP": {  # Optional - will be auto-discovered if not provided
        "host": "smtp.example.com",
        "port": 587,
        "use_ssl": True,
        "protocol": "SMTP"
    },
    # Optional: Add a custom tracking parameter to all redirected links
    "TRACKING_PARAMETER_ID": "unicom_tid",  # Default is 'unicom_tid', omit to disable
    # Optional: Control when emails are marked as seen in IMAP. Options: 'on_save', 'on_request_completed', 'on_request_completed' (default)
    "MARK_SEEN_WHEN": "on_request_completed"
}

channel = Channel.objects.create(
    name="My Email Channel",
    platform="Email",
    config=email_config
)
```

#### Telegram Channel
```python
# Only API token is required - webhook secret is auto-generated
telegram_config = {
    "API_TOKEN": "your-telegram-bot-token"
}

channel = Channel.objects.create(
    name="My Telegram Bot",
    platform="Telegram",
    config=telegram_config
)
```

### Message Handling

#### Sending Messages
```python
# Send an email
channel.send_message({
    'to': ['recipient@example.com'],
    'subject': 'Hello',
    'html': '<h1>Hello World</h1>'
})

# Send a Telegram message
channel.send_message({
    'chat_id': '123456789',
    'text': 'Hello Telegram!'
})

# Reply to a message
message.reply_with({
    'text': 'This is a reply'
})
```

#### Using Templates
```python
from unicom.models import MessageTemplate

template = MessageTemplate.objects.create(
    title='Welcome Email',
    content='<h1>Welcome {{name}}!</h1>',
    category='Onboarding'
)

# Make template available for specific channels
template.channels.add(email_channel)
```

#### Scheduling Messages
```python
from unicom.models import DraftMessage
from django.utils import timezone

draft = DraftMessage.objects.create(
    channel=channel,
    to=['recipient@example.com'],
    subject='Scheduled Email',
    html='<h1>This is scheduled</h1>',
    send_at=timezone.now() + timezone.timedelta(hours=24),
    is_approved=True,
    status='scheduled'
)
```

---

## 🧑‍💻 Contributing

We ❤️ contributors!

### Requirements:

* Docker & Docker Compose installed

### Getting Started:

1. Clone the repo:

   ```bash
   git clone https://github.com/meena-erian/unicom.git
   cd unicom
   ```

2. Create a `db.env` file in the root:

   ```env
   POSTGRES_DB=unicom_test
   POSTGRES_USER=unicom
   POSTGRES_PASSWORD=unicom
   DJANGO_PUBLIC_ORIGIN=https://yourdomain.com
   # Needed if you want to use the rich-text email composer in the admin
   UNICOM_TINYMCE_API_KEY=your-tinymce-api-key
   # Needed if you want to use the AI template population service
   OPENAI_API_KEY=your-openai-api-key
   ```

3. Start the dev environment:

   ```bash
   docker-compose up --build
   ```

4. Run tests:

   ```bash
   docker-compose exec app pytest
   ```

   or just

   ```bash
   pytest
   ```
   Note: To run ```test_telegram_live``` tests you need to create ```telegram_credentials.py``` in the tests folder and define in it ```TELEGRAM_API_TOKEN``` and ```TELEGRAM_SECRET_TOKEN``` and to run ```test_email_live``` you need to create ```email_credentials.py``` in the tests folder and define in it ```EMAIL_CONFIG``` dict with the properties ```EMAIL_ADDRESS```: str, ```EMAIL_PASSWORD```: str, and ```IMAP```: dict, and ```SMTP```: dict, each of ```IMAP``` and ```SMTP``` contains ```host```:str ,```port```:int, ```use_ssl```:bool, ```protocol```: (```IMAP``` | ```SMTP```)  

No need to modify `settings.py` — everything is pre-wired to read from `db.env`.

---

## 📄 License

MIT License © Meena (Menas) Erian

## 📦 Release Automation

To release a new version to PyPI:

1. Ensure your changes are committed and pushed.
2. Run:
   
   ```bash
   make release VERSION=1.2.3
   ```
   This will:
   - Tag the release as v1.2.3 in Git
   - Push the tag
   - Build the package
   - Upload to PyPI using your .pypirc

3. For an auto-generated version based on date/time, just run:
   
   ```bash
   make release
   ```
   This will use the current date/time as the version (e.g., 2024.06.13.1530).

The version is automatically managed by setuptools_scm from Git tags and is available at runtime as `unicom.__version__`.
