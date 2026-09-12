import paramiko
import sys
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'
local_zip = r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\deploy_root.zip'
remote_zip = '/root/deploy_root.zip'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=120)
    print("Connected successfully!")
    
    print(f"Uploading archive...")
    with SCPClient(ssh.get_transport()) as scp:
        scp.put(local_zip, remote_zip)
    print("Upload complete!")
    
    commands = [
        "mkdir -p /root/InstrumentPSK",
        "unzip -o /root/deploy_root.zip -d /root/InstrumentPSK",
        "cd /root/InstrumentPSK && docker-compose down",
        "cd /root/InstrumentPSK && docker-compose up -d --build"
    ]
    
    for cmd in commands:
        print(f"\n>>> Executing: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        
        for line in stdout:
            sys.stdout.write(line)
        for line in stderr:
            sys.stderr.write(line)
            
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            print(f"Command '{cmd}' failed with exit status {exit_status}")
            
    print("\nDeployment completed successfully!")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    ssh.close()
