import paramiko
import sys
import os
from scp import SCPClient
import time

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

# FORCE SYNC SOURCE CODE
# We ensure that the source files in the container are EXACTLY what we want
container_files = [
    ('DjangoWebProject1/app/static/app/css/quick-view.css', '/app/app/static/app/css/quick-view.css'),
    ('DjangoWebProject1/app/static/app/js/quick-view.js', '/app/app/static/app/js/quick-view.js'),
    ('DjangoWebProject1/app/views.py', '/app/app/views.py'),
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
        for local_path, container_abs_path in container_files:
            full_local_path = os.path.join(r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1', local_path)
            temp_path = f'/tmp/{os.path.basename(local_path)}'
            print(f"Pushing {local_path} -> {container_abs_path}")
            scp.put(full_local_path, temp_path)
            ssh.exec_command(f'docker cp {temp_path} {web_container}:{container_abs_path}')
            ssh.exec_command(f'rm {temp_path}')

    # FORCE COLLECTSTATIC TO SHARED VOLUME
    print("Running collectstatic...")
    ssh.exec_command(f"docker exec {web_container} python manage.py collectstatic --noinput --clear")
    
    print("Restarting web...")
    ssh.exec_command(f"docker restart {web_container}")
    
    print("\nDONE. Please test with Ctrl+F5.")

except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
