import paramiko
import sys
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'
local_zip = r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\deploy_root.zip'
remote_zip = '/root/deploy_final_v3.zip'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=30)
    print("Connected successfully!")
    
    # Upload archive
    print(f"Uploading final code...")
    with SCPClient(ssh.get_transport()) as scp:
        scp.put(local_zip, remote_zip)
    
    commands = [
        # 1. Kill old app completely
        "cd /root/app && docker-compose down -v || true",
        "rm -rf /root/app",
        
        # 2. Unpack to correct location
        "mkdir -p /root/InstrumentPSK",
        "unzip -o /root/deploy_final_v3.zip -d /root/InstrumentPSK",
        
        # 3. CRITICAL: Rebuild the image so it bakes in the new templates and URLs
        "cd /root/InstrumentPSK && docker-compose up -d --build",
        
        # 4. Cleanup zip
        "rm /root/deploy_final_v3.zip"
    ]
    
    for cmd in commands:
        print(f"\n>>> Executing: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        for line in stdout: sys.stdout.write(line)
        for line in stderr: sys.stderr.write(line)
        
    print("\nRE-DEPLOYMENT FINISHED!")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    ssh.close()
