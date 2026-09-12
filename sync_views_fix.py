import paramiko
import sys
import os
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# File to sync
local_path = r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\views.py'
container_path = '/app/app/views.py'
host_path = '/root/InstrumentPSK/DjangoWebProject1/app/views.py'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=30)
    print("Connected!")
    
    stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}" | grep web')
    web_container = stdout.read().decode().strip()
    
    with SCPClient(ssh.get_transport()) as scp:
        temp_path = f'/tmp/views.py'
        print(f"Pushing views.py...")
        scp.put(local_path, temp_path)
        
        # Update host
        ssh.exec_command(f'cp {temp_path} {host_path}')
        # Update container
        ssh.exec_command(f'docker cp {temp_path} {web_container}:{container_path}')
        ssh.exec_command(f'rm {temp_path}')

    print("Restarting web container...")
    ssh.exec_command(f"docker restart {web_container}")
    
    print("\nVIEWS FIX APPLIED SUCCESSFULLY!")

except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
