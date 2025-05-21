import pytest
from unittest.mock import patch
from unicom.models import BotCredentials

# Smart mock simulating Telegram API behavior
def mock_set_telegram_webhook(bot_credentials):
    token = bot_credentials.config.get("TELEGRAM_API_TOKEN")
    if not token:
        return {"ok": False, "description": "Missing token"}
    if token.startswith("fail"):
        return {"ok": False, "description": "Invalid token"}
    return {"ok": True, "result": "Webhook set"}

@patch("unicom.services.telegram.set_telegram_webhook", side_effect=mock_set_telegram_webhook)
def test_valid_telegram_webhook(mock_func):
    bot = BotCredentials(name="ValidBot", platform="Telegram", config={
        "TELEGRAM_API_TOKEN": "valid_token",
        "TELEGRAM_SECRET_TOKEN": "secret"
    })
    bot.validate()
    assert bot.active is True
    assert bot.error is None

@patch("unicom.services.telegram.set_telegram_webhook", side_effect=mock_set_telegram_webhook)
def test_invalid_token_telegram_webhook(mock_func):
    bot = BotCredentials(name="InvalidBot", platform="Telegram", config={
        "TELEGRAM_API_TOKEN": "fail_token"
    })
    bot.validate()
    assert bot.active is False
    assert bot.error == "Invalid token"

@patch("unicom.services.telegram.set_telegram_webhook", side_effect=Exception("Network failure"))
def test_exception_handling_telegram_webhook(mock_func):
    bot = BotCredentials(name="CrashBot", platform="Telegram", config={
        "TELEGRAM_API_TOKEN": "crash_token"
    })
    bot.validate()
    assert bot.active is False
    assert "Failed to set Telegram webhook" in bot.error