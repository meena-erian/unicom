# Django Unicom

**Unified communication layer for Django** — easily integrate Telegram bots, WhatsApp, and Email with a consistent API across all platforms.

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

That's it! Unicom can now register and manage public-facing webhooks (e.g., for Telegram bots) based on your defined base URL.

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
