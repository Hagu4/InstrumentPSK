import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

cmd = '''cd /root/InstrumentPSK && docker-compose exec -T web sh -c "echo \\\"\\nALLOWED_HOSTS = ['*']\\\" >> DjangoWebProject1/settings.py" && docker-compose restart web'''
ssh.exec_command(cmd)

ssh.close()
