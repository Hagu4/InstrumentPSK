import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('45.146.164.80', username='root', password='REMOVED_SECRET')

stdin, stdout, stderr = ssh.exec_command('docker logs instrumentpsk-web-1 --tail 500')
logs = stdout.read().decode()
error_logs = stderr.read().decode()

print("STDOUT LOGS:")
print(logs)
print("\nSTDERR LOGS:")
print(error_logs)

ssh.close()
