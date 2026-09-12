import paramiko
import sys
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=120)

with open('prod_fix.py', 'w', encoding='utf-8') as f:
    f.write("""
import re
path = 'DjangoWebProject1/settings.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. ALLOWED_HOSTS
content = re.sub(r"ALLOWED_HOSTS\s*=\s*\[.*?\]", "ALLOWED_HOSTS = ['*', 'instrumentpsk.ru', 'www.instrumentpsk.ru', '45.146.164.80']", content)

# 2. CSRF_TRUSTED_ORIGINS
if 'CSRF_TRUSTED_ORIGINS' not in content:
    content += "\\nCSRF_TRUSTED_ORIGINS = ['https://instrumentpsk.ru', 'https://www.instrumentpsk.ru']\\n"

# 3. Security headers
if 'SECURE_PROXY_SSL_HEADER' not in content:
    content += "\\nSECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')\\n"

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Production settings applied successfully.')
""")

with SCPClient(ssh.get_transport()) as scp:
    scp.put('prod_fix.py', '/root/InstrumentPSK/prod_fix.py')

commands = [
    "cd /root/InstrumentPSK && docker cp prod_fix.py instrumentpsk-web-1:/app/prod_fix.py",
    "cd /root/InstrumentPSK && docker-compose exec -T web python /app/prod_fix.py",
    "cd /root/InstrumentPSK && docker-compose restart web",
    "cd /root/InstrumentPSK && docker-compose restart nginx"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
print("\nVerified.")
