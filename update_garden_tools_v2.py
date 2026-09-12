import paramiko
import sys
from scp import SCPClient

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

with open('garden_fix_v2.py', 'w', encoding='utf-8') as f:
    f.write("""
from app.models import Category, Product

parent = Category.objects.filter(name='Садовая техника').first()
if not parent:
    print('Parent category not found')
    exit()

def get_or_create_safe(name, parent, slug):
    # Try to find by name first
    cat = Category.objects.filter(name=name, parent=parent).first()
    if cat:
        return cat
    
    # Check if slug exists anywhere
    if Category.objects.filter(slug=slug).exists():
        slug = f"{slug}-garden"
        if Category.objects.filter(slug=slug).exists():
             import time
             slug = f"{slug}-{int(time.time())}"
             
    return Category.objects.create(name=name, parent=parent, slug=slug)

# 1. Split "Бензопилы и пилы цепные электрические"
mixed_saws = Category.objects.filter(parent=parent, name='Бензопилы и пилы цепные электрические').first()
if mixed_saws:
    benzo_saws = get_or_create_safe('Бензопилы', parent, 'benzopily')
    electro_saws = get_or_create_safe('Электропилы', parent, 'elektropily')
    
    for p in Product.objects.filter(category=mixed_saws):
        t = p.title.lower()
        if 'бензо' in t:
            p.category = benzo_saws
        elif any(w in t for w in ['электрическая', 'аккум']):
            p.category = electro_saws
        else:
            p.category = benzo_saws if 'цепь' in t or 'шина' in t else electro_saws
        p.save()
    
    if not Product.objects.filter(category=mixed_saws).exists():
        mixed_saws.delete()
        print('Split Saws category.')

# 2. Split "Воздуходувки и опрыскиватели бензиновые"
mixed_blowers = Category.objects.filter(parent=parent, name='Воздуходувки и опрыскиватели бензиновые').first()
if mixed_blowers:
    blowers = get_or_create_safe('Воздуходувки', parent, 'vozdukhoduvki')
    sprayers = get_or_create_safe('Опрыскиватели', parent, 'opryskivateli')
    
    for p in Product.objects.filter(category=mixed_blowers):
        t = p.title.lower()
        if 'воздуходувк' in t:
            p.category = blowers
        else:
            p.category = sprayers
        p.save()
    
    if not Product.objects.filter(category=mixed_blowers).exists():
        mixed_blowers.delete()
        print('Split Blowers category.')

# 3. Split "Газонокосилки, мотокосы и триммеры"
mixed_mowers = Category.objects.filter(parent=parent, name='Газонокосилки, мотокосы и триммеры').first()
if mixed_mowers:
    mowers = get_or_create_safe('Газонокосилки', parent, 'gazonokosilki')
    trimmers = get_or_create_safe('Триммеры и косы', parent, 'trimmery-i-kosy')
    
    for p in Product.objects.filter(category=mixed_mowers):
        t = p.title.lower()
        if 'газонокосилка' in t or 'нож для газонокосилки' in t:
            p.category = mowers
        else:
            p.category = trimmers
        p.save()
        
    if not Product.objects.filter(category=mixed_mowers).exists():
        mixed_mowers.delete()
        print('Split Mowers category.')

print('DONE')
""")

with SCPClient(ssh.get_transport()) as scp:
    scp.put('garden_fix_v2.py', '/root/InstrumentPSK/garden_fix_v2.py')

commands = [
    "cd /root/InstrumentPSK && docker cp garden_fix_v2.py instrumentpsk-web-1:/app/garden_fix_v2.py",
    "cd /root/InstrumentPSK && docker-compose exec -T web python manage.py shell < garden_fix_v2.py"
]

for cmd in commands:
    print(f"Executing: {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    for line in stdout: sys.stdout.write(line)
    for line in stderr: sys.stderr.write(line)

ssh.close()
