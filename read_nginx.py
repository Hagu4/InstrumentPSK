import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

stdin, stdout, stderr = ssh.exec_command('cat /root/InstrumentPSK/nginx.conf')
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

stdin, stdout, stderr = ssh.exec_command('docker logs instrumentpsk-nginx-1 --tail 10')
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
