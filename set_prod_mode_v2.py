import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

# Set DEBUG back to False
cmd = "cd /root/InstrumentPSK && docker-compose exec -T web sed -i 's|DEBUG=True|DEBUG=False|g' .env && docker-compose restart web"
print("Setting DEBUG=False and restarting...")
stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
