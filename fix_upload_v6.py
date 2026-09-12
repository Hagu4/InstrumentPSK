import paramiko
import sys
import os
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# Files to sync
files_to_sync = [
    ('DjangoWebProject1/app/models.py', 'app/models.py'),
    ('nginx.conf', '../nginx.conf'), # Relative to DjangoWebProject1 folder on host
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=30)
    print("Connected successfully!")
    
    # 1. Identify container names
    stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}"')
    containers = stdout.read().decode().splitlines()
    web_container = None
    nginx_container = None
    for c in containers:
        if 'web' in c: web_container = c
        if 'nginx' in c: nginx_container = c
    
    if not web_container or not nginx_container:
        print(f"Containers not found! web: {web_container}, nginx: {nginx_container}")
        sys.exit(1)
    
    print(f"Using web: {web_container}, nginx: {nginx_container}")
    
    # 2. Upload and copy files
    with SCPClient(ssh.get_transport()) as scp:
        # Sync models.py
        local_models = r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\models.py'
        remote_temp = '/tmp/models.py'
        scp.put(local_models, remote_temp)
        ssh.exec_command(f'cp {remote_temp} /root/InstrumentPSK/DjangoWebProject1/app/models.py')
        ssh.exec_command(f'docker cp {remote_temp} {web_container}:/app/app/models.py')
        ssh.exec_command(f'rm {remote_temp}')
        print("models.py synced.")

        # Sync nginx.conf
        local_nginx = r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\nginx.conf'
        remote_temp_nginx = '/tmp/nginx.conf'
        scp.put(local_nginx, remote_temp_nginx)
        ssh.exec_command(f'cp {remote_temp_nginx} /root/InstrumentPSK/nginx.conf')
        # Nginx config is usually mounted as a volume, but to be sure we restart the container
        ssh.exec_command(f'rm {remote_temp_nginx}')
        print("nginx.conf synced.")

    # 3. Restart containers
    print("Restarting containers...")
    ssh.exec_command(f'docker restart {web_container}')
    ssh.exec_command(f'docker restart {nginx_container}')
    
    print("\nFIX APPLIED SUCCESSFULLY! Try uploading images now.")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    ssh.close()
