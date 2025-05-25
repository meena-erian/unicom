import os
import time
import json
import pytest
from django.test import Client
from unicom.models import Channel
from tests.utils import wait_for_condition
from tests.telegram_credentials import TELEGRAM_API_TOKEN, TELEGRAM_SECRET_TOKEN
from django.db import connections


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestTelegramLive:
    @pytest.fixture(autouse=True)
    def setup(self, db):
        # Create a superuser for admin interface tests
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='password'
        )
        self.client = Client()
    
    def _wait_bot(self, pk, *, cond, timeout=5):
        return wait_for_condition(
            lambda: cond(Channel.objects.get(pk=pk)),
            timeout=timeout
        )

    def test_missing_secret_token(self):
        """
        Valid token but no secret -> expect automatic generation of secret token
        and successful webhook set
        """
        bot = Channel(
            name="NoSecretBot",
            platform="Telegram",
            config={
                "TELEGRAM_API_TOKEN": TELEGRAM_API_TOKEN
            }
        )
        bot.save()
        # time.sleep(1)
        self._wait_bot(bot.pk, cond=lambda b: b.active is True)
        bot.refresh_from_db()
        assert bot.active is True
        assert bot.error is None
        assert "TELEGRAM_SECRET_TOKEN" in bot.config
        assert bot.config["TELEGRAM_SECRET_TOKEN"] is not None
        assert bot.config["TELEGRAM_SECRET_TOKEN"] != ""
        connections.close_all()

    def test_with_valid_credentials(self):
        """
        Both token and secret provided -> expect successful webhook set
        """
        bot = Channel(
            name="ValidBot",
            platform="Telegram",
            config={
                "TELEGRAM_API_TOKEN": TELEGRAM_API_TOKEN,
                "TELEGRAM_SECRET_TOKEN": TELEGRAM_SECRET_TOKEN
            }
        )
        bot.save()
        # time.sleep(1)
        self._wait_bot(bot.pk, cond=lambda b: b.active is True)
        bot.refresh_from_db()
        assert bot.active is True
        assert bot.error is None

    def test_invalid_token_admin_interface(self):
        """
        Submit invalid token via admin -> page should render with error message
        """
        assert self.client.login(username='admin', password='password')
        url = '/admin/unicom/channel/add/'
        data = {
            'name': 'InvalidBot',
            'platform': 'Telegram',
            'config': json.dumps({
                "TELEGRAM_API_TOKEN": "invalid_token",
                "TELEGRAM_SECRET_TOKEN": TELEGRAM_SECRET_TOKEN
            })
        }
        response = self.client.post(url, data, follow=True)
        content = response.content.decode().lower()
        bot = Channel.objects.get(name="InvalidBot")
        self._wait_bot(bot.pk, cond=lambda b: b.error is not None)
        bot.refresh_from_db()
        assert response.status_code == 200
        assert bot.active is False
        assert 'Unauthorized' in bot.error or 'Not Found' in bot.error

        
