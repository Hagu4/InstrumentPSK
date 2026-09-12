
from app.models import Category, Product

parent = Category.objects.filter(name='Ручной инструмент').first()
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
    'Инструмент для разметки': ('Разметка', 'razmetka'),
    'Малярный инструмент': ('Малярный', 'malyarnyi'),
    'Металлообрабатывающий инструмент': ('По металлу', 'po-metallu'),
    'Общестроительный инструмент': ('Строительный', 'stroitelnyi'),
    'Штукатурно-отделочный инструмент': ('Отделочный', 'otdelochnyi')
}

for old, (new, slug) in renames.items():
    c = Category.objects.filter(parent=parent, name=old).first()
    if c:
        safe_save(c, new, slug)
        print(f'Renamed: {old} -> {new}')

# 2. Split "Слесарно-столярный инструмент"
big_cat = Category.objects.filter(parent=parent, name='Слесарно-столярный инструмент').first()
if big_cat:
    hammer_cat, _ = Category.objects.get_or_create(name='Ударный и топоры', parent=parent, defaults={'slug': 'udarnyi-i-topory'})
    saw_cat, _ = Category.objects.get_or_create(name='Пилы и ножи', parent=parent, defaults={'slug': 'pily-i-nozhi'})
    pliers_cat, _ = Category.objects.get_or_create(name='Шарнирно-губцевый', parent=parent, defaults={'slug': 'sharnirno-gubtsevyi'})
    keys_cat, _ = Category.objects.get_or_create(name='Ключи и отвертки', parent=parent, defaults={'slug': 'klyuchi-i-otvertki'})
    st_cat, _ = Category.objects.get_or_create(name='Слесарно-столярный', parent=parent, defaults={'slug': 'slesarno-stolyarnyi-fixed'})

    products = Product.objects.filter(category=big_cat)
    for p in products:
        title = p.title.lower()
        if any(w in title for w in ['молоток', 'кувалда', 'топор', 'колун', 'киянка', 'зубило']):
            p.category = hammer_cat
        elif any(w in title for w in ['ножовка', 'пила', 'нож ', 'нож,', 'лезвие', 'стамеск']):
            p.category = saw_cat
        elif any(w in title for w in ['плоскогубцы', 'пассатижи', 'кусачки', 'клещи', 'бокорезы', 'тонкогубцы', 'щипцы']):
            p.category = pliers_cat
        elif any(w in title for w in ['ключ', 'отвертк', 'вороток', 'головка', 'бита']):
            p.category = keys_cat
        else:
            p.category = st_cat
        p.save()
    
    if not Product.objects.filter(category=big_cat).exists():
        big_cat.delete()
        print('Split and removed original large category.')

print('DONE')
