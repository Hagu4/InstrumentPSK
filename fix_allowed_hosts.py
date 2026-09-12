import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

commands = [
    "cd /root/InstrumentPSK && docker-compose exec -T web sed -i \"s|ALLOWED_HOSTS = \\['localhost', '127.0.0.1'\\]|ALLOWED_HOSTS = \\['localhost', '127.0.0.1', 'instrumentpsk.ru', 'www.instrumentpsk.ru', '45.146.164.80'\\]|g\" DjangoWebProject1/settings.py",
    "cd /root/InstrumentPSK && docker-compose restart web"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
