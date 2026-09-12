import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

# Check for hardcoded text
cmd1 = "docker exec instrumentpsk-web-1 grep -r 'Весенняя распродажа' /app/app/templates"
# Check for Promotion objects in DB
cmd2 = "docker exec instrumentpsk-web-1 python manage.py shell -c 'from app.models import Promotion; print([(p.title, p.subtitle) for p in Promotion.objects.all()])'"

print("Searching for banner source...")
for cmd in [cmd1, cmd2]:
    print(f"\nExecuting: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
