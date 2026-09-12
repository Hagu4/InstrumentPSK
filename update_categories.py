import paramiko
import sys

host = '45.146.164.80'
user = 'root'
password = 'REMOVED_SECRET'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(host, username=user, password=password, timeout=30)

remote_script = """
from app.models import Category, Product

parent = Category.objects.filter(name='Измерительный инструмент').first()
if not parent:
    print('Parent category not found')
    exit()

def safe_save_category(cat, new_name, new_slug):
    cat.name = new_name
    cat.slug = new_slug
    try:
        cat.save()
        print('Updated: ' + new_name)
    except:
        cat.slug = new_slug + '-' + str(cat.id)
        cat.save()
        print('Updated with suffix: ' + new_name)

# 1. Renames
renames = {
    'Нивелиры лазерные и построители плоскостей': ('Лазерные уровни', 'lazernye-urovni'),
    'Рулетки, мерные ленты': ('Рулетки', 'ruletki'),
    'Дорожные измерительные приборы': ('Курвиметры', 'kurvimetry'),
    'Принадлежности для измерительного оборудования': ('Аксессуары', 'aksessuary')
}

for old_name, (new_name, new_slug) in renames.items():
    cat = Category.objects.filter(parent=parent, name=old_name).first()
    if cat:
        safe_save_category(cat, new_name, new_slug)

# 2. Split Mixed Category
mixed_cat_name = 'Детекторы проводки, пирометры, тепловизоры'
mixed_cat = Category.objects.filter(parent=parent, name=mixed_cat_name).first()

if mixed_cat:
    det_name = 'Детекторы и сканеры'
    det_slug = 'detektory-i-skanery'
    teplo_name = 'Тепловизоры и пирометры'
    teplo_slug = 'teplovizory-i-pirometry'
    
    det_cat = Category.objects.filter(name=det_name, parent=parent).first()
    if not det_cat:
        det_cat = Category.objects.create(name=det_name, parent=parent, slug=det_slug)
    
    teplo_cat = Category.objects.filter(name=teplo_name, parent=parent).first()
    if not teplo_cat:
        teplo_cat = Category.objects.create(name=teplo_name, parent=parent, slug=teplo_slug)
    
    products = Product.objects.filter(category=mixed_cat)
    for p in products:
        title_lower = p.title.lower()
        if 'тепловизор' in title_lower or 'пирометр' in title_lower:
            p.category = teplo_cat
            print('Moved: ' + p.title[:30] + '... -> ' + teplo_name)
        else:
            p.category = det_cat
            print('Moved: ' + p.title[:30] + '... -> ' + det_name)
        p.save()
            
    if not Product.objects.filter(category=mixed_cat).exists():
        mixed_cat.delete()
        print('Deleted old category: ' + mixed_cat_name)

print('DONE')
"""

cmd = f"docker exec instrumentpsk-web-1 python manage.py shell -c \"{remote_script}\""
stdin, stdout, stderr = ssh.exec_command(cmd)
for line in stdout: sys.stdout.write(line)
for line in stderr: sys.stderr.write(line)

ssh.close()
