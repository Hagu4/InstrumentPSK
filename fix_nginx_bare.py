import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

conf = """
server {
    listen 80;
    server_name instrumentpsk.ru www.instrumentpsk.ru;
    
    location / {
        proxy_pass http://172.19.0.4:8000;
        proxy_set_header Host $host;
    }
}
"""

commands = [
    f"cat << 'EOF' > /root/InstrumentPSK/nginx.conf\n{conf}EOF",
    "cd /root/InstrumentPSK && docker-compose restart nginx"
]

for cmd in commands:
    ssh.exec_command(cmd)

ssh.close()
