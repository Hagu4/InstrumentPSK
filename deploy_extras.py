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
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\DjangoWebProject1\settings.py', '/app/DjangoWebProject1/settings.py'),
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\DjangoWebProject1\urls.py', '/app/DjangoWebProject1/urls.py'),
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\views.py', '/app/app/views.py'),
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\sitemaps.py', '/app/app/sitemaps.py'),
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\404.html', '/app/app/templates/app/404.html'),
    (r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\500.html', '/app/app/templates/app/500.html'),
]

try:
    with SCPClient(ssh.get_transport()) as scp:
        for local_p, remote_container_p in files_to_sync:
            # Get filename
            fname = local_p.split('\\')[-1]
            temp_remote = f"/root/{fname}"
            print(f"Uploading {local_p}...")
            scp.put(local_p, temp_remote)
            
            # Copy into container
            cmd = f"docker cp {temp_remote} instrumentpsk-web-1:{remote_container_p}"
            ssh.exec_command(cmd)

    print("Restarting web to apply Sitemap & Error pages...")
    ssh.exec_command("cd /root/InstrumentPSK && docker-compose restart web")
    print("Done!")

finally:
    ssh.close()
