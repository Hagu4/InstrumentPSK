import paramiko
import sys
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

# Create a local file with the python code to fix CSRF
with open('remote_csrf_fix.py', 'w') as f:
    f.write("""
path = 'DjangoWebProject1/settings.py'
with open(path, 'r') as f:
    content = f.read()

csrf_setting = "\\nCSRF_TRUSTED_ORIGINS = ['https://instrumentpsk.ru', 'https://www.instrumentpsk.ru']\\n"

if 'CSRF_TRUSTED_ORIGINS' not in content:
    with open(path, 'a') as f_out:
        f_out.write(csrf_setting)
    print('CSRF_TRUSTED_ORIGINS added.')
else:
    print('CSRF_TRUSTED_ORIGINS already exists, manual check might be needed if it still fails.')
""")

with SCPClient(ssh.get_transport()) as scp:
    scp.put('remote_csrf_fix.py', '/root/InstrumentPSK/remote_csrf_fix.py')

commands = [
    "cd /root/InstrumentPSK && docker cp remote_csrf_fix.py instrumentpsk-web-1:/app/remote_csrf_fix.py",
    "cd /root/InstrumentPSK && docker-compose exec -T web python /app/remote_csrf_fix.py",
    "cd /root/InstrumentPSK && docker-compose restart web"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
print("\nCSRF Fix applied.")
