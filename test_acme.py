import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

commands = [
    "mkdir -p /root/InstrumentPSK/certbot/www/.well-known/acme-challenge/",
    "echo 'test_success' > /root/InstrumentPSK/certbot/www/.well-known/acme-challenge/test.txt",
    "docker exec instrumentpsk-nginx-1 curl -s http://localhost/.well-known/acme-challenge/test.txt || echo 'curl failed'"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
