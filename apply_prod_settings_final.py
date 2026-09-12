import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=120)

# Robustly apply all production settings at once
python_script = """
import re
path = 'DjangoWebProject1/settings.py'
with open(path, 'r') as f:
    content = f.read()

# 1. ALLOWED_HOSTS
content = re.sub(r"ALLOWED_HOSTS\s*=\s*\[.*?\]", "ALLOWED_HOSTS = ['*', 'instrumentpsk.ru', 'www.instrumentpsk.ru', '45.146.164.80']", content)

# 2. CSRF_TRUSTED_ORIGINS
csrf_line = "\\nCSRF_TRUSTED_ORIGINS = ['https://instrumentpsk.ru', 'https://www.instrumentpsk.ru']\\n"
if 'CSRF_TRUSTED_ORIGINS' not in content:
    content += csrf_line

# 3. Security headers
if 'SECURE_PROXY_SSL_HEADER' not in content:
    content += "\\nSECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')\\n"

with open(path, 'w') as f:
    f.write(content)
print('Production settings applied.')
"""

# Execute inside the container
cmd = f'''cd /root/InstrumentPSK && docker-compose exec -T web python -c "{python_script}" && docker-compose restart web'''

print("Applying production settings...")
stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
print("\nDone.")
