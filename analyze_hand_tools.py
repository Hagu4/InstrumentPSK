import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=120)

remote_script = """
from app.models import Category, Product

parent = Category.objects.filter(name='Ручной инструмент').first()
if not parent:
    print('Parent category not found')
    exit()

print('Subcategories:')
subs = Category.objects.filter(parent=parent)
for s in subs:
    print(f'- {s.name} ({Product.objects.filter(category=s).count()} items)')

# Sample 20 products from SleSarno-Stolyarniy
big_cat = Category.objects.filter(parent=parent, name='Слесарно-столярный инструмент').first()
if big_cat:
    print('\\nSample products from SleSarno-Stolyarniy:')
    prods = Product.objects.filter(category=big_cat)[:30]
    for p in prods:
        print(f'  * {p.title}')
"""

cmd = f"docker exec instrumentpsk-web-1 python manage.py shell -c \"{remote_script}\""
stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
ssh.close()
