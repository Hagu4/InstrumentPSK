import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

print("--- RUNNING CONTAINERS ---")
stdin, stdout, stderr = ssh.exec_command("docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Image}}'")
for line in stdout: sys.stdout.write(line)

print("\n--- CHECKING NEW URLS.PY ---")
stdin, stdout, stderr = ssh.exec_command("cat /root/InstrumentPSK/DjangoWebProject1/DjangoWebProject1/urls.py | grep path")
for line in stdout: sys.stdout.write(line)

print("\n--- CHECKING NEW INDEX.HTML ---")
stdin, stdout, stderr = ssh.exec_command("grep 'Профессиональный инструмент' /root/InstrumentPSK/DjangoWebProject1/app/templates/app/index.html")
for line in stdout: sys.stdout.write(line)

print("\n--- CHECKING OLD APP URLS.PY ---")
stdin, stdout, stderr = ssh.exec_command("cat /root/app/DjangoWebProject1/DjangoWebProject1/urls.py | grep path")
for line in stdout: sys.stdout.write(line)

ssh.close()
