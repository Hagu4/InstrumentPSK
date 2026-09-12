import paramiko
import sys
import os
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# Files to sync
files_to_sync = [
    ('DjangoWebProject1/app/static/app/css/catalog_redesign.css', 'app/static/app/css/catalog_redesign.css'),
    ('DjangoWebProject1/app/templates/app/index.html', 'app/templates/app/index.html'),
    ('DjangoWebProject1/app/templates/app/product_detail.html', 'app/templates/app/product_detail.html'),
    ('DjangoWebProject1/app/templates/app/layout.html', 'app/templates/app/layout.html'),
    ('DjangoWebProject1/app/templates/app/warranty.html', 'app/templates/app/warranty.html'),
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
        # Fallback if grep failed
        stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}"')
        containers = stdout.read().decode().splitlines()
        for c in containers:
            if 'web' in c:
                container_name = c
                break
    
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
    
    # 3. Run collectstatic and restart gunicorn (by sending HUP signal or just restarting container)
    print("Running collectstatic inside container...")
    ssh.exec_command(f'docker exec {container_name} python manage.py collectstatic --noinput')
    
    # Restarting gunicorn is often needed for template changes if they are cached
    # Since we are using gunicorn in docker, restarting the container is the simplest way to clear caches
    print("Restarting web container to apply template changes...")
    ssh.exec_command(f'docker restart {container_name}')
    
    print("\nSYNC FINISHED SUCCESSFULLY!")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    ssh.close()
