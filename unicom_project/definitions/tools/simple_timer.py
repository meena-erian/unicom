# Simple timer tool - wrapper around time.sleep()
import time

def simple_timer(seconds: int, message: str = "Timer finished!") -> str:
    """
    Wait for specified seconds then respond. Uses time.sleep().
    """
    try:
        if seconds < 1 or seconds > 300:  # Limit to 5 minutes max
            return "Timer must be between 1 and 300 seconds."

        time.sleep(seconds)
        return f"⏰ {message} (Waited {seconds} seconds)"

    except Exception as e:
        return f"Timer error: {str(e)}"

tool_definition = {
    "name": "simple_timer",
    "description": "Wait for a specified number of seconds before responding. Uses Python's time.sleep().",
    "parameters": {
        "seconds": {
            "type": "integer",
            "description": "Number of seconds to wait (1-300)"
        },
        "message": {
            "type": "string",
            "description": "Custom message to return after timer expires",
            "default": "Timer finished!"
        }
    },
    "run": simple_timer
}