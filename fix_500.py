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
    
    # Read the file
    stdin, stdout, stderr = ssh.exec_command("docker exec instrumentpsk-web-1 cat /app/DjangoWebProject1/settings.py")
    content = stdout.read().decode()
    
    # 1. Ensure ALLOWED_HOSTS is wildcard for now to eliminate it as a suspect
    content = content.replace("ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'instrumentpsk.ru', 'www.instrumentpsk.ru', '45.146.164.80']", "ALLOWED_HOSTS = ['*']")
    
    # 2. Fix the redundant WHITENOISE_MANIFEST_STRICT
    lines = content.splitlines()
    new_lines = []
    seen_strict = False
    for line in lines:
        if "WHITENOISE_MANIFEST_STRICT" in line:
            if seen_strict: continue
            seen_strict = True
        new_lines.append(line)
    content = "\n".join(new_lines)
    
    # 3. Create a temporary file on the server
    remote_temp = "/tmp/settings_fixed.py"
    with ssh.open_sftp() as sftp:
        with sftp.file(remote_temp, 'w') as f:
            f.write(content)
            
    # 4. Copy it back into the container
    ssh.exec_command(f"docker cp {remote_temp} instrumentpsk-web-1:/app/DjangoWebProject1/settings.py")
    
    # 5. Restart
    ssh.exec_command("docker restart instrumentpsk-web-1")
    
    print("Emergency settings fix applied and web restarted.")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
