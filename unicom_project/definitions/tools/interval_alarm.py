# Interval alarm tool - wrapper around threading.Timer()
import threading
from unicom.models import Message

def interval_alarm(interval_seconds: int, repeat_count: int, alarm_message: str = "Alarm!") -> str:
    """
    Send multiple alarm messages at specified intervals using threading.Timer().
    """
    try:
        if interval_seconds < 1 or interval_seconds > 60:
            return "Interval must be between 1 and 60 seconds."

        if repeat_count < 1 or repeat_count > 10:
            return "Repeat count must be between 1 and 10."

        def send_alarm(count):
            if count <= repeat_count:
                # Create new message for this alarm
                alarm_text = f"🔔 {alarm_message} (Alert {count}/{repeat_count})"
                Message.objects.create(
                    content=alarm_text,
                    sender=account,
                    parent_message=message,
                    is_from_bot=True
                )

                # Schedule next alarm
                if count < repeat_count:
                    timer = threading.Timer(interval_seconds, send_alarm, [count + 1])
                    timer.daemon = True
                    timer.start()

        # Start first alarm
        timer = threading.Timer(interval_seconds, send_alarm, [1])
        timer.daemon = True
        timer.start()

        return f"⏰ Interval alarm set! Will send {repeat_count} alerts every {interval_seconds} seconds."

    except Exception as e:
        return f"Alarm error: {str(e)}"

tool_definition = {
    "name": "interval_alarm",
    "description": "Set an interval alarm that sends multiple messages at specified intervals using threading.Timer().",
    "parameters": {
        "interval_seconds": {
            "type": "integer",
            "description": "Interval between alarms in seconds (1-60)"
        },
        "repeat_count": {
            "type": "integer",
            "description": "Number of alarms to send (1-10)"
        },
        "alarm_message": {
            "type": "string",
            "description": "Custom alarm message",
            "default": "Alarm!"
        }
    },
    "run": interval_alarm
}