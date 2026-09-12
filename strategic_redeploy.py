import paramiko
import sys
import os
from scp import SCPClient
import time

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# Files to sync to host paths (for persistence)
host_files = [
    ('DjangoWebProject1/app/templates/app/index.html', 'DjangoWebProject1/app/templates/app/index.html'),
]

# Files to sync into web container's internal folders
# Format: (local_path, container_absolute_path)
container_files = [
    ('DjangoWebProject1/app/templates/app/index.html', '/app/app/templates/app/index.html'),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def get_containers():
    stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}"')
    return stdout.read().decode().splitlines()

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=30)
    print("Connected successfully!")
    
    # 1. Upload files to host project dir
    with SCPClient(ssh.get_transport()) as scp:
        for local_path, remote_suffix in host_files:
            full_local_path = os.path.join(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1', local_path)
            remote_path = f'/root/InstrumentPSK/{remote_suffix}'
            print(f"Uploading {local_path} to {remote_path}...")
            ssh.exec_command(f"mkdir -p {os.path.dirname(remote_path)}")
            scp.put(full_local_path, remote_path)

    # 2. Update containers config
    print("\nUpdating Docker containers...")
    ssh.exec_command("cd /root/InstrumentPSK && docker-compose up -d")
    time.sleep(5)
    
    containers = get_containers()
    web_container = next((c for c in containers if 'web' in c), None)
    nginx_container = next((c for c in containers if 'nginx' in c), None)
    
    if not web_container:
        print(f"Web container not found! Current: {containers}")
        sys.exit(1)
    
    print(f"Detected containers: Web={web_container}, Nginx={nginx_container}")

    # 3. Sync files directly into container using absolute paths
    with SCPClient(ssh.get_transport()) as scp:
        for local_path, container_abs_path in container_files:
            full_local_path = os.path.join(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1', local_path)
            temp_path = f'/tmp/{os.path.basename(local_path)}'
            print(f"Syncing {local_path} to container {container_abs_path}...")
            scp.put(full_local_path, temp_path)
            ssh.exec_command(f'docker cp {temp_path} {web_container}:{container_abs_path}')
            ssh.exec_command(f'rm {temp_path}')

    # 4. NUCLEAR COLLECTSTATIC
    print("\n>>> PERFORMING NUCLEAR REFRESH...")
    # Based on our new settings: STATIC_ROOT = '/app/staticfiles'
    cmds = [
        f"docker exec {web_container} python manage.py migrate --noinput",
        f"docker exec {web_container} rm -rf /app/staticfiles/*",
        f"docker exec {web_container} python manage.py collectstatic --noinput",
        f"docker restart {web_container}",
        f"docker restart {nginx_container}"
    ]
    
    for cmd in cmds:
        print(f"Executing: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())

    print("\nREDEPLOYMENT FINISHED! PLEASE CLEAR CACHE (Ctrl+F5).")
    
except Exception as e:
    import traceback
    print(f"An error occurred: {e}")
    traceback.print_exc()
finally:
    ssh.close()
