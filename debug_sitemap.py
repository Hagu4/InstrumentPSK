import paramiko
import sys
import time

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=120)

print("Starting log tail...")
# Use curl to trigger a request
ssh.exec_command('curl -k -I https://instrumentpsk.ru/sitemap.xml')
time.sleep(1)

stdin, stdout, stderr = ssh.exec_command('docker logs instrumentpsk-web-1 --tail 10')
for line in stdout: sys.stdout.write(line)

ssh.close()
