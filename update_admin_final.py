import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

# Python script to run inside the container to delete the old admin and create the new one
remote_python_script = """
from django.contrib.auth.models import User
# Delete old admin if exists
User.objects.filter(username='admin').delete()

# Create new superuser
if not User.objects.filter(username='Hagu').exists():
    User.objects.create_superuser('Hagu', 'vgromyko64@gmail.com', 'REMOVED_SECRET')
    print('User Hagu created successfully')
else:
    u = User.objects.get(username='Hagu')
    u.set_password('REMOVED_SECRET')
    u.email = 'vgromyko64@gmail.com'
    u.save()
    print('User Hagu updated successfully')
"""

# Format the command to execute the script inside the docker container
cmd = f'''cd /root/InstrumentPSK && docker-compose exec -T web python manage.py shell -c "{remote_python_script}"'''

print("Updating administrator accounts...")
stdin, stdout, stderr = ssh.exec_command(cmd)

# Capture and print output
for line in stdout:
    sys.stdout.write(line)
for line in stderr:
    sys.stderr.write(line)

ssh.close()
print("\nDone.")
