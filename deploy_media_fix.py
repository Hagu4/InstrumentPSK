import paramiko
import sys
import os
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# Files to sync
files_to_sync = [
    ('docker-compose.yml', 'docker-compose.yml'),
    ('nginx.conf', 'nginx.conf'),
    ('DjangoWebProject1/app/models.py', 'DjangoWebProject1/app/models.py'),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=120)
    print("Connected successfully!")
    
    # 1. Upload files to the host project directory
    with SCPClient(ssh.get_transport()) as scp:
        for local_path, remote_suffix in files_to_sync:
            full_local_path = os.path.join(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1', local_path)
            remote_path = f'/root/InstrumentPSK/{remote_suffix}'
            
            print(f"Uploading {local_path} to {remote_path}...")
            scp.put(full_local_path, remote_path)

    # 2. Re-apply docker-compose to update volumes for Nginx
    print("\nRestarting containers with updated docker-compose...")
    commands = [
        "cd /root/InstrumentPSK && docker-compose up -d",
        "docker restart instrumentpsk-web-1", # Restart web to pick up models.py if it was copied via docker cp or if it was volume mounted (it is not volume mounted, so we need docker cp)
    ]

    # Handle models.py sync into container
    print("Updating models.py inside container...")
    ssh.exec_command(f'docker cp /root/InstrumentPSK/DjangoWebProject1/app/models.py instrumentpsk-web-1:/app/app/models.py')
    
    for cmd in commands:
        print(f"Executing: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())
    
    print("\nDEPLOYMENT OF MEDIA FIX FINISHED!")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    ssh.close()
