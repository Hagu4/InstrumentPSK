import paramiko
import sys
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=120)

files_to_sync = [
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\views.py', '/app/app/views.py'),
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\errors\404_custom.html', '/app/app/templates/app/errors/404_custom.html'),
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\errors\500_custom.html', '/app/app/templates/app/errors/500_custom.html'),
]

try:
    with SCPClient(ssh.get_transport()) as scp:
        # Create remote dir first
        ssh.exec_command("docker exec instrumentpsk-web-1 mkdir -p /app/app/templates/app/errors")
        
        for local_p, remote_container_p in files_to_sync:
            # Upload to host
            fname = local_p.split('\\')[-1]
            temp_remote = f"/root/{fname}"
            scp.put(local_p, temp_remote)
            
            # Copy into container
            cmd = f"docker cp {temp_remote} instrumentpsk-web-1:{remote_container_p}"
            ssh.exec_command(cmd)

    print("Restarting web to apply unique Error pages...")
    ssh.exec_command("cd /root/InstrumentPSK && docker-compose restart web")
    print("Done!")

finally:
    ssh.close()
