import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host} for heavy diagnostics...")
    ssh.connect(host, username=user, password=password, timeout=30)
    
    print("\n--- [1] SYSTEM & SECURITY CHECK ---")
    commands = [
        "cat /root/InstrumentPSK/DjangoWebProject1/.env | grep DEBUG",
        "docker exec instrumentpsk-web-1 python manage.py check --deploy",
        "curl -sI -k https://instrumentpsk.ru | grep -E 'HTTP|Strict-Transport-Security'"
    ]
    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        for line in stdout: sys.stdout.write(line)

    print("\n--- [2] DATABASE CONSISTENCY CHECK ---")
    db_cmd = '''docker exec instrumentpsk-web-1 python manage.py shell -c "
from app.models import Product, Category, Brand, Order
print(f'Total Products: {Product.objects.count()}')
print(f'Total Categories: {Category.objects.count()}')
print(f'Total Brands: {Brand.objects.count()}')
print(f'Latest 5 Products: {[p.title[:20] for p in Product.objects.order_by(\\\'-id\\\')[:5]]}')
"'''
    stdin, stdout, stderr = ssh.exec_command(db_cmd)
    for line in stdout: sys.stdout.write(line)

    print("\n--- [3] LIVE PAGE RESPONSE TEST ---")
    urls = [
        "https://instrumentpsk.ru/",
        "https://instrumentpsk.ru/catalog/",
        "https://instrumentpsk.ru/cart/",
        "https://instrumentpsk.ru/useful-resources/"
    ]
    for url in urls:
        stdin, stdout, stderr = ssh.exec_command(f"curl -o /dev/null -s -w '%{{http_code}}' -k {url}")
        code = stdout.read().decode().strip()
        print(f"URL: {url} -> Status: {code}")

    print("\n--- [4] STATIC ASSETS ACCESSIBILITY ---")
    static_cmd = "curl -o /dev/null -s -w '%{http_code}' -k https://instrumentpsk.ru/static/app/content/site.css"
    stdin, stdout, stderr = ssh.exec_command(static_cmd)
    print(f"Main CSS -> Status: {stdout.read().decode().strip()}")

    print("\n--- [5] ERROR LOG SCAN (LAST 50 LINES) ---")
    stdin, stdout, stderr = ssh.exec_command("docker logs instrumentpsk-web-1 --tail 50")
    logs = stdout.read().decode()
    if "Traceback" in logs or "Error" in logs:
        print("ALERT: Potential errors found in logs!")
        print(logs[-500:])
    else:
        print("Clean logs. No critical tracebacks found.")

except Exception as e:
    print(f"An error occurred during testing: {e}")
finally:
    ssh.close()
