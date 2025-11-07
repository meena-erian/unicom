# System information tool - wrapper around Python's platform module
import platform
import os
import sys

def get_system_info() -> str:
    """
    Get system information using Python's built-in platform module.
    """
    try:
        info = []
        info.append(f"System: {platform.system()}")
        info.append(f"Platform: {platform.platform()}")
        info.append(f"Machine: {platform.machine()}")
        info.append(f"Processor: {platform.processor()}")
        info.append(f"Python Version: {platform.python_version()}")
        info.append(f"Architecture: {platform.architecture()[0]}")
        info.append(f"Node Name: {platform.node()}")
        info.append(f"Process ID: {os.getpid()}")
        info.append(f"Working Directory: {os.getcwd()}")

        return "🖥️ System Information:\n" + "\n".join(info)
    except Exception as e:
        return f"Error getting system info: {str(e)}"

tool_definition = {
    "name": "get_system_info",
    "description": "Get detailed system information using Python's platform module.",
    "parameters": {},
    "run": get_system_info
}