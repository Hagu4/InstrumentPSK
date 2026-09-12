import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

commands = [
    # 1. Set DEBUG=False in the .env file on the host (context)
    "cd /root/InstrumentPSK/DjangoWebProject1 && sed -i 's|DEBUG=True|DEBUG=False|g' .env",
    
    # 2. Update docker-compose to use more gunicorn workers (e.g. 3 workers for a 1GB RAM machine)
    "cd /root/InstrumentPSK && sed -i 's|gunicorn --bind 0.0.0.0:8000|gunicorn --workers 3 --threads 2 --bind 0.0.0.0:8000|gunicorn' docker-compose.yml",
    
    # 3. Rebuild and restart to apply .env and compose changes
    "cd /root/InstrumentPSK && docker-compose up -d --build"
]

for cmd in commands:
    print(f"\n>>> Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
print("\nSpeed optimization applied.")
