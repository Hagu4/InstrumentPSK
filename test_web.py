import urllib.request
import sys

try:
    response = urllib.request.urlopen('http://localhost:8000/management-psk-zone/')
    content = response.read().decode()
    print("CSS Link found:", "admin_custom.css" in content)
    # Find the line with the CSS link
    for line in content.splitlines():
        if "admin_custom.css" in line:
            print("Line:", line.strip())
except Exception as e:
    print(f"Error: {e}")
    if hasattr(e, 'read'):
        print(e.read().decode())
