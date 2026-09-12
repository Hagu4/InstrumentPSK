
from app.models import Category, Product

parent = Category.objects.filter(name='Садовая техника').first()
if not parent:
    print('Parent category not found')
    exit()

def safe_save(cat, name, slug):
    cat.name = name
    cat.slug = slug
    try:
        cat.save()
    except:
        cat.slug = slug + '-' + str(cat.id)
        cat.save()

# 1. Simple Renames
renames = {
    'Аккум. ножницы садовые, секаторы, ножовки': ('Секаторы и ножницы', 'sekatory-i-nozhnitsy'),
    'Аэраторы газона': ('Аэраторы', 'aeratory'),
    'Культиваторы и мотоблоки': ('Культиваторы', 'kultivatory'),
    'Насосы и насосные станции': ('Насосы', 'nasosy'),
    'Снегоуборочная техника': ('Снегоуборщики', 'snegouborshchiki')
}

for old, (new, slug) in renames.items():
    c = Category.objects.filter(parent=parent, name=old).first()
    if c:
        safe_save(c, new, slug)
        print(f'Renamed: {old} -> {new}')

# 2. Split "Бензопилы и пилы цепные электрические"
mixed_saws = Category.objects.filter(parent=parent, name='Бензопилы и пилы цепные электрические').first()
if mixed_saws:
    benzo_saws, _ = Category.objects.get_or_create(name='Бензопилы', parent=parent, defaults={'slug': 'benzopily'})
    electro_saws, _ = Category.objects.get_or_create(name='Электропилы', parent=parent, defaults={'slug': 'elektropily'})
    
    for p in Product.objects.filter(category=mixed_saws):
        t = p.title.lower()
        if 'бензо' in t:
            p.category = benzo_saws
        elif any(w in t for w in ['электрическая', 'аккум']):
            p.category = electro_saws
        else:
            # Fallback based on name for specific parts
            p.category = benzo_saws if 'цепь' in t or 'шина' in t else electro_saws
        p.save()
    
    if not Product.objects.filter(category=mixed_saws).exists():
        mixed_saws.delete()
        print('Split Saws category.')

# 3. Split "Воздуходувки и опрыскиватели бензиновые"
mixed_blowers = Category.objects.filter(parent=parent, name='Воздуходувки и опрыскиватели бензиновые').first()
if mixed_blowers:
    blowers, _ = Category.objects.get_or_create(name='Воздуходувки', parent=parent, defaults={'slug': 'vozdukhoduvki'})
    sprayers, _ = Category.objects.get_or_create(name='Опрыскиватели', parent=parent, defaults={'slug': 'opryskivateli'})
    
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

# 4. Split "Газонокосилки, мотокосы и триммеры"
mixed_mowers = Category.objects.filter(parent=parent, name='Газонокосилки, мотокосы и триммеры').first()
if mixed_mowers:
    mowers, _ = Category.objects.get_or_create(name='Газонокосилки', parent=parent, defaults={'slug': 'gazonokosilki'})
    trimmers, _ = Category.objects.get_or_create(name='Триммеры и косы', parent=parent, defaults={'slug': 'trimmery-i-kosy'})
    
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
