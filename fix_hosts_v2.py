import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

# Create a local file with the python code to avoid escaping hell
with open('remote_fix.py', 'w') as f:
    f.write("""
import re
path = 'DjangoWebProject1/settings.py'
with open(path, 'r') as f:
    content = f.read()
# Use a very simple string replace first to avoid regex issues
target = "ALLOWED_HOSTS = ['localhost', '127.0.0.1']"
replacement = "ALLOWED_HOSTS = ['*', 'instrumentpsk.ru', 'www.instrumentpsk.ru', '45.146.164.80']"
if target in content:
    content = content.replace(target, replacement)
else:
    # Fallback to a simpler regex if the string doesn't match exactly
    content = re.sub(r"ALLOWED_HOSTS\s*=\s*\[.*?\]", replacement, content)
with open(path, 'w') as f:
    f.write(content)
print('Settings updated.')
""")

from scp import SCPClient
with SCPClient(ssh.get_transport()) as scp:
    scp.put('remote_fix.py', '/root/InstrumentPSK/remote_fix.py')

commands = [
    "cd /root/InstrumentPSK && docker cp remote_fix.py instrumentpsk-web-1:/app/remote_fix.py",
    "cd /root/InstrumentPSK && docker-compose exec -T web python /app/remote_fix.py",
    "cd /root/InstrumentPSK && docker-compose restart web"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
print("\nDone.")
