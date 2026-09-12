import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

commands = [
    "cd /root/InstrumentPSK && sed -i 's|return 301 https://$host$request_uri;|proxy_pass http://web:8000;|g' nginx.conf",
    "cd /root/InstrumentPSK && sed -i 's|listen 443 ssl;|listen 443 ssl default_server; ssl_reject_handshake on;|g' nginx.conf",
    "cd /root/InstrumentPSK && sed -i 's|ssl_certificate |#ssl_certificate |g' nginx.conf",
    "cd /root/InstrumentPSK && docker-compose restart nginx"
]

for cmd in commands:
    stdin, stdout, stderr = ssh.exec_command(cmd)

ssh.close()
