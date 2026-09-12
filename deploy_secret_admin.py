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
    # Upload main urls.py
    scp.put(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\DjangoWebProject1\urls.py', 
            '/root/InstrumentPSK/DjangoWebProject1/DjangoWebProject1/urls.py')
    # Upload layout.html
    scp.put(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\layout.html', 
            '/root/InstrumentPSK/DjangoWebProject1/app/templates/app/layout.html')

commands = [
    "cd /root/InstrumentPSK && docker-compose restart web",
]

for cmd in commands:
    print(f"Executing: {cmd}")
    ssh.exec_command(cmd)

ssh.close()
print("Secret admin path deployed to server.")
