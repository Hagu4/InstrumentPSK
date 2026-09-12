import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

commands = [
    "mkdir -p /root/InstrumentPSK/certbot/conf/live/instrumentpsk.ru",
    "openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /root/InstrumentPSK/certbot/conf/live/instrumentpsk.ru/privkey.pem -out /root/InstrumentPSK/certbot/conf/live/instrumentpsk.ru/fullchain.pem -subj '/CN=instrumentpsk.ru'",
    "cp /root/InstrumentPSK/nginx.conf.bak /root/InstrumentPSK/nginx.conf", # Assuming I can just upload the proper one
]

conf = """
server {
    listen 80;
    server_name instrumentpsk.ru www.instrumentpsk.ru;
    server_tokens off;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name instrumentpsk.ru www.instrumentpsk.ru;
    server_tokens off;

    ssl_certificate /etc/letsencrypt/live/instrumentpsk.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/instrumentpsk.ru/privkey.pem;

    location / {
        proxy_pass http://instrumentpsk-web-1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        proxy_pass http://instrumentpsk-web-1:8000/static/;
    }

    location /media/ {
        proxy_pass http://instrumentpsk-web-1:8000/media/;
    }
}
"""

ssh.exec_command(f"cat << 'EOF' > /root/InstrumentPSK/nginx.conf\n{conf}EOF")

for cmd in commands:
    ssh.exec_command(cmd)

ssh.exec_command("cd /root/InstrumentPSK && docker-compose restart nginx")
print("Dummy SSL configured")

ssh.close()
