import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=120)

commands = [
    "cd /root/InstrumentPSK && docker-compose exec -T web python manage.py createsuperuser --noinput --username admin --email admin@instrumentpsk.ru",
    "cd /root/InstrumentPSK && docker-compose exec -T web python manage.py shell -c \"from django.contrib.auth.models import User; u = User.objects.get(username='admin'); u.set_password('REMOVED_SECRET'); u.save()\""
]

for cmd in commands:
    stdin, stdout, stderr = ssh.exec_command(cmd)

ssh.close()
