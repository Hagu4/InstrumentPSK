import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

cmd = "docker exec instrumentpsk-certbot-1 certbot certonly --webroot -w /var/www/certbot -d instrumentpsk.ru -d www.instrumentpsk.ru --email admin@instrumentpsk.ru --agree-tos --no-eff-email --force-renewal"

stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
