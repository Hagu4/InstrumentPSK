import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

# 1. Create superuser via environment variables to avoid prompt
# 2. Force set password in shell to be 100% sure
cmd = '''cd /root/InstrumentPSK && docker-compose exec -T web sh -c "DJANGO_SUPERUSER_PASSWORD=REMOVED_SECRET DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_EMAIL=admin@instrumentpsk.ru python manage.py createsuperuser --noinput || true"'''
print("Creating superuser...")
stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

cmd2 = '''cd /root/InstrumentPSK && docker-compose exec -T web python manage.py shell -c "from django.contrib.auth.models import User; u = User.objects.get(username='admin'); u.set_password('REMOVED_SECRET'); u.save()"'''
print("\nSetting password...")
stdin, stdout, stderr = ssh.exec_command(cmd2)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
print("\nDone.")
