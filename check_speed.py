import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=120)

commands = [
    "free -h",
    "top -bn1 | head -n 5",
    "docker stats --no-stream",
    "cat /root/InstrumentPSK/DjangoWebProject1/.env | grep DEBUG"
]

for cmd in commands:
    print(f"\n>>> Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
