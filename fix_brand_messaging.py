import paramiko
import sys
import os
from scp import SCPClient
import time

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# CRITICAL BRAND MESSAGING FILES
templates_to_fix = [
    ('DjangoWebProject1/app/templates/app/index.html', '/app/app/templates/app/index.html'),
    ('DjangoWebProject1/app/templates/app/product_detail.html', '/app/app/templates/app/product_detail.html'),
    ('DjangoWebProject1/app/templates/app/warranty.html', '/app/app/templates/app/warranty.html'),
    ('DjangoWebProject1/app/templates/app/layout.html', '/app/app/templates/app/layout.html'),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=30)
    print("Connected successfully!")
    
    stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}" | grep web')
    web_container = stdout.read().decode().strip()
    
    if not web_container:
        print("Web container not found!")
        sys.exit(1)
    
    print(f"Syncing brand fixes to container: {web_container}")

    with SCPClient(ssh.get_transport()) as scp:
        for local_path, container_abs_path in templates_to_fix:
            full_local_path = os.path.join(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1', local_path)
            temp_path = f'/tmp/{os.path.basename(local_path)}'
            
            print(f"Syncing {local_path}...")
            scp.put(full_local_path, temp_path)
            
            # Sync to HOST project dir (for persistence after compose up)
            host_path = f'/root/InstrumentPSK/{local_path}'
            ssh.exec_command(f"mkdir -p {os.path.dirname(host_path)}")
            ssh.exec_command(f'cp {temp_path} {host_path}')
            
            # Sync to CONTAINER (for immediate effect)
            ssh.exec_command(f'docker cp {temp_path} {web_container}:{container_abs_path}')
            ssh.exec_command(f'rm {temp_path}')

    print("\nRestarting container to refresh template cache...")
    ssh.exec_command(f"docker restart {web_container}")
    
    print("\nBRAND MESSAGING RESTORED SUCCESSFULLY!")
    print("Please check: 3 years warranty, Pickup, and Best Price should be back.")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    ssh.close()
