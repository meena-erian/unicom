# Django Unicom

**Unified communication layer for Django** — easily integrate Telegram bots, WhatsApp, and Email with a consistent API across all platforms.

---

## 🚀 Quick Start

1. **Install the package:**
   ```bash
   pip install django-unicom
   ```

2. **Add `unicom` to your Django settings:**

   ```python
   INSTALLED_APPS = [
       ...
       'unicom',
   ]
   ```

3. **Include `unicom` URLs in your project’s `urls.py`:**

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

That’s it! Unicom can now register and manage public-facing webhooks (e.g., for Telegram bots) based on your defined base URL.

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
   Note: To run ```test_telegram_live``` tests you need to create ```telegram_credentials.py``` in the tests folder and define in it ```TELEGRAM_API_TOKEN``` and ```TELEGRAM_SECRET_TOKEN```

No need to modify `settings.py` — everything is pre-wired to read from `db.env`.

---

## 📄 License

MIT License © Meena (Menas) Erian
