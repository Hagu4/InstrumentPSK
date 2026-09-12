import paramiko
import sys
import os
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# Files to sync for UI fix (Admin + Quick View)
files_to_sync = [
    ('DjangoWebProject1/app/static/app/css/admin_custom.css', 'app/static/app/css/admin_custom.css'),
    ('DjangoWebProject1/app/static/app/css/quick-view.css', 'app/static/app/css/quick-view.css'),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=30)
    print("Connected successfully!")
    
    # 1. Identify container name
    stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}" | grep web')
    container_name = stdout.read().decode().strip()
    
    if not container_name:
        print("Could not find web container!")
        sys.exit(1)
    
    print(f"Using container: {container_name}")
    
    # 2. Upload and copy files
    with SCPClient(ssh.get_transport()) as scp:
        for local_path, remote_suffix in files_to_sync:
            full_local_path = os.path.join(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1', local_path)
            temp_remote_path = f'/tmp/{os.path.basename(local_path)}'
            
            print(f"Syncing {local_path}...")
            scp.put(full_local_path, temp_remote_path)
            
            # Copy to host project dir
            host_project_path = f'/root/InstrumentPSK/DjangoWebProject1/{remote_suffix}'
            ssh.exec_command(f'cp {temp_remote_path} {host_project_path}')
            
            # Copy into container
            container_app_path = f'/app/{remote_suffix}'
            ssh.exec_command(f'docker cp {temp_remote_path} {container_name}:{container_app_path}')
            
            # Cleanup temp
            ssh.exec_command(f'rm {temp_remote_path}')
    
    # 3. Run collectstatic and restart container
    print("Running collectstatic inside container...")
    ssh.exec_command(f'docker exec {container_name} python manage.py collectstatic --noinput')
    
    print("Restarting web container to apply CSS changes...")
    ssh.exec_command(f'docker restart {container_name}')
    
    print("\nUI FIXES APPLIED SUCCESSFULLY!")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    ssh.close()
