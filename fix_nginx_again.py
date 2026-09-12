import paramiko
import sys
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

with SCPClient(ssh.get_transport()) as scp:
    scp.put(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\nginx_temp.conf', '/root/InstrumentPSK/nginx.conf')

commands = [
    "cd /root/InstrumentPSK && docker-compose restart nginx",
    "cd /root/InstrumentPSK && docker-compose ps nginx",
]

for cmd in commands:
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
