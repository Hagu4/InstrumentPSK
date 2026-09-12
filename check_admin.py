import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=120)

cmd = '''cd /root/InstrumentPSK && docker-compose exec -T web python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(username='admin').exists())"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
