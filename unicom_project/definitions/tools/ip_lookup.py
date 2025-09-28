# IP lookup tool - wrapper around requests library
import requests
import socket

def ip_lookup(target: str = "self") -> str:
    """
    Look up IP information using requests library and external services.
    """
    try:
        if target.lower() == "self":
            # Get own public IP
            response = requests.get("https://httpbin.org/ip", timeout=10)
            response.raise_for_status()
            data = response.json()
            ip = data.get("origin", "Unknown")

            # Get more info about the IP
            info_response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=10)
            if info_response.status_code == 200:
                info_data = info_response.json()
                result = f"🌐 Your IP Information:\n"
                result += f"IP Address: {info_data.get('ip', 'Unknown')}\n"
                result += f"Location: {info_data.get('city', 'Unknown')}, {info_data.get('region', 'Unknown')}, {info_data.get('country', 'Unknown')}\n"
                result += f"ISP: {info_data.get('org', 'Unknown')}\n"
                result += f"Timezone: {info_data.get('timezone', 'Unknown')}"
                return result
            else:
                return f"🌐 Your Public IP: {ip}"

        else:
            # Look up specific IP or domain
            try:
                # Try to resolve as domain first
                ip = socket.gethostbyname(target)
            except socket.gaierror:
                # Assume it's already an IP
                ip = target

            # Get info about the IP
            response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=10)
            response.raise_for_status()
            data = response.json()

            result = f"🌐 IP Information for {target}:\n"
            result += f"IP Address: {data.get('ip', 'Unknown')}\n"
            result += f"Location: {data.get('city', 'Unknown')}, {data.get('region', 'Unknown')}, {data.get('country', 'Unknown')}\n"
            result += f"ISP: {data.get('org', 'Unknown')}\n"
            result += f"Timezone: {data.get('timezone', 'Unknown')}"
            return result

    except requests.RequestException as e:
        return f"Network error during IP lookup: {str(e)}"
    except Exception as e:
        return f"IP lookup error: {str(e)}"

tool_definition = {
    "name": "ip_lookup",
    "description": "Look up IP address information using external services. Can check your own IP or look up specific IPs/domains.",
    "parameters": {
        "target": {
            "type": "string",
            "description": "IP address, domain name, or 'self' to check your own IP",
            "default": "self"
        }
    },
    "run": ip_lookup
}