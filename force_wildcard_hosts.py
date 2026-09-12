import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

cmd = '''cd /root/InstrumentPSK && docker-compose exec -T web python -c "
path = 'DjangoWebProject1/settings.py'
with open(path, 'r') as f:
    content = f.read()
import re
new_content = re.sub(r\"ALLOWED_HOSTS = \[.*?\]\", \"ALLOWED_HOSTS = ['*']\", content)
with open(path, 'w') as f:
    f.write(new_content)
" && docker-compose restart web'''

stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
