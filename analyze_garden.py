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

parent = Category.objects.filter(name='Садовая техника').first()
if not parent:
    print('Parent category not found')
    exit()

print('Subcategories of Garden Equipment:')
subs = Category.objects.filter(parent=parent)
for s in subs:
    print(f'- {s.name} ({Product.objects.filter(category=s).count()} items)')

# Check for top-level electric/gas categories
electro = Category.objects.filter(name='Электроинструмент').first()
benzo = Category.objects.filter(name='Бензоинструмент').first()
print(f'\\nTop level categories found: Electro={bool(electro)}, Benzo={bool(benzo)}')

# Sample 10 products from the largest mixed category to see titles
mixed = Category.objects.filter(parent=parent, name='Газонокосилки, мотокосы и триммеры').first()
if mixed:
    print('\\nSample from Mowers/Trimmers:')
    for p in Product.objects.filter(category=mixed)[:15]:
        print(f'  * {p.title}')

mixed_saws = Category.objects.filter(parent=parent, name='Бензопилы и пилы цепные электрические').first()
if mixed_saws:
    print('\\nSample from Saws:')
    for p in Product.objects.filter(category=mixed_saws)[:15]:
        print(f'  * {p.title}')
"""

cmd = f"docker exec instrumentpsk-web-1 python manage.py shell -c \"{remote_script}\""
stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
ssh.close()
