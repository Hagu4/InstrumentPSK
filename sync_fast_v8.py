import paramiko
import sys
import os
from scp import SCPClient
import time

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# FILES TO SYNC
files_to_sync = [
    ('DjangoWebProject1/DjangoWebProject1/settings.py', '/app/DjangoWebProject1/settings.py'),
    ('DjangoWebProject1/app/static/app/css/admin_custom_v4.css', '/app/app/static/app/css/admin_custom_v4.css'),
    ('DjangoWebProject1/app/templates/app/product_detail.html', '/app/app/templates/app/product_detail.html'),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=30)
    print("Connected!")
    
    stdin, stdout, stderr = ssh.exec_command('docker ps --format "{{.Names}}" | grep web')
    web_container = stdout.read().decode().strip()
    
    with SCPClient(ssh.get_transport()) as scp:
        for local_path, container_abs_path in files_to_sync:
            full_local_path = os.path.join(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1', local_path)
            temp_path = f'/tmp/{os.path.basename(local_path)}'
            print(f"Syncing {local_path} -> {container_abs_path}")
            scp.put(full_local_path, temp_path)
            ssh.exec_command(f'docker cp {temp_path} {web_container}:{container_abs_path}')
            
            # Manually ensure staticfiles copy for v4
            if '.css' in local_path:
                 ssh.exec_command(f'docker exec {web_container} mkdir -p /app/staticfiles/app/css')
                 ssh.exec_command(f'docker exec {web_container} cp {container_abs_path} /app/staticfiles/app/css/{os.path.basename(local_path)}')
            
            ssh.exec_command(f'rm {temp_path}')

    # RECOLLECT
    print("Running collectstatic...")
    ssh.exec_command(f"docker exec {web_container} python manage.py collectstatic --noinput --clear")
    
    print("Restarting web...")
    ssh.exec_command(f"docker restart {web_container}")
    
    print("\nREINFORCED ADMIN FIX V4 APPLIED! Please test with Ctrl+F5.")

except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
