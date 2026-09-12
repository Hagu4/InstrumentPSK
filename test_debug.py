import paramiko
import sys
import os

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(host, username=user, password=password, timeout=30)
    print("Connected!")
    
    # Temporarily set DEBUG=True in settings.py inside container
    cmd = "docker exec instrumentpsk-web-1 sed -i \"s/DEBUG = os.environ.get('DEBUG', 'True') == 'True'/DEBUG = True/\" /app/DjangoWebProject1/settings.py"
    ssh.exec_command(cmd)
    
    # Restart to apply
    ssh.exec_command("docker restart instrumentpsk-web-1")
    print("DEBUG set to True and web restarted.")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
