import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

commands = [
    "cd /root/InstrumentPSK && docker-compose exec -T web sed -i 's|D:/Studies/Lab and pars/Web-ProgDJ(2)/DjangoWebProject1/|/app/|g' app/management/commands/load_supplier.py",
    "cd /root/InstrumentPSK && docker-compose exec -T web python manage.py load_supplier"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
