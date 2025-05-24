import time
import pytest
from django.test import Client
from unicom.models import Bot
from tests.utils import wait_for_condition
from tests.email_credentials import EMAIL_CONFIG
from django.db import connections


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestEmailLive:
    @pytest.fixture(autouse=True)
    def setup(self, db):
        # Create a superuser if you want to test admin interface later
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='password'
        )
        self.client = Client()

    def _wait_bot(self, pk, *, cond, timeout=10):
        return wait_for_condition(
            lambda: cond(Bot.objects.get(pk=pk)),
            timeout=timeout
        )

    def test_with_explicit_valid_credentials(self):
        """
        Provide full EMAIL_CONFIG (IMAP + SMTP + ADDRESS + PASSWORD) -> expect active=True
        """
        bot = Bot(
            name="EmailBotExplicitValid",
            platform="Email",
            config=EMAIL_CONFIG
        )
        bot.save()
        self._wait_bot(bot.pk, cond=lambda b: b.active is True)
        bot.refresh_from_db()
        assert bot.active is True
        assert bot.error is None
        connections.close_all()

    def test_without_explicit_config_valid(self):
        """
        Provide only EMAIL_ADDRESS + EMAIL_PASSWORD -> expect autodetect succeeds
        """
        partial = {
            "EMAIL_ADDRESS": EMAIL_CONFIG["EMAIL_ADDRESS"],
            "EMAIL_PASSWORD": EMAIL_CONFIG["EMAIL_PASSWORD"],
        }
        bot = Bot(
            name="EmailBotAutoValid",
            platform="Email",
            config=partial
        )
        bot.save()
        self._wait_bot(bot.pk, cond=lambda b: b.active is True)
        bot.refresh_from_db()
        assert bot.active is True
        assert bot.error is None
        connections.close_all()

    def test_with_explicit_invalid_password(self):
        """
        Full config but wrong password -> expect active=False and error set
        """
        bad = dict(EMAIL_CONFIG)
        bad["EMAIL_PASSWORD"] = "wrong-password"
        bot = Bot(
            name="EmailBotExplicitInvalid",
            platform="Email",
            config=bad
        )
        bot.save()
        self._wait_bot(bot.pk, cond=lambda b: b.error is not None)
        bot.refresh_from_db()
        assert bot.active is False
        assert bot.error is not None
        connections.close_all()

    def test_without_explicit_config_invalid(self):
        """
        Only address+wrong password -> autodetect + auth failure
        """
        bad_auto = {
            "EMAIL_ADDRESS": EMAIL_CONFIG["EMAIL_ADDRESS"],
            "EMAIL_PASSWORD": "wrong-password",
        }
        bot = Bot(
            name="EmailBotAutoInvalid",
            platform="Email",
            config=bad_auto
        )
        bot.save()
        self._wait_bot(bot.pk, cond=lambda b: b.error is not None)
        bot.refresh_from_db()
        assert bot.active is False
        assert bot.error is not None
        connections.close_all()
