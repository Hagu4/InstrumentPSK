import paramiko
import sys
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'
local_file = r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\export_universal_2026-06-16_1781596138_6a30ffea07f2a.xlsx'
remote_file = '/root/InstrumentPSK/export.xlsx'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

print(f"Uploading xlsx...")
with SCPClient(ssh.get_transport()) as scp:
    scp.put(local_file, remote_file)

commands = [
    "cd /root/InstrumentPSK && docker cp export.xlsx instrumentpsk-web-1:/app/export.xlsx",
    "cd /root/InstrumentPSK && docker-compose exec -T web sed -i 's|/app/export_universal_2026-06-16_1781596138_6a30ffea07f2a.xlsx|/app/export.xlsx|g' app/management/commands/load_supplier.py",
    "cd /root/InstrumentPSK && docker-compose exec -T web python manage.py load_supplier"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
