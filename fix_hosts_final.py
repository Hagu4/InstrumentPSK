import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

# We will replace the entire line for ALLOWED_HOSTS to be sure
cmd = '''cd /root/InstrumentPSK && docker-compose exec -T web python -c "
import re
with open('DjangoWebProject1/settings.py', 'r') as f:
    content = f.read()
new_content = re.sub(r\"ALLOWED_HOSTS = \[.*?\]\", \"ALLOWED_HOSTS = ['*', 'instrumentpsk.ru', 'www.instrumentpsk.ru', '45.146.164.80']\", content)
with open('DjangoWebProject1/settings.py', 'w') as f:
    f.write(new_content)
" && docker-compose restart web'''

print("Updating ALLOWED_HOSTS...")
stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
print("\nDone.")
