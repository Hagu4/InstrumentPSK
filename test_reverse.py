import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

cmd = """docker exec instrumentpsk-web-1 python manage.py shell -c "
from django.urls import reverse
print(f'Home: {reverse(\\\"home\\\")}')
from app.sitemaps import StaticViewSitemap
s = StaticViewSitemap()
print(f'Sitemap items: {s.items()}')
" """

stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
