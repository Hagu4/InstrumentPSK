import os
import requests
import pandas as pd
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from app.models import Category, Brand, Product, ProductImage, Characteristic, ProductCharacteristic

def transliterate(text):
    if not text:
        return ""
    dic = {'а':'a', 'б':'b', 'в':'v', 'г':'g', 'д':'d', 'е':'e', 'ё':'yo',
      'ж':'zh', 'з':'z', 'и':'i', 'й':'y', 'к':'k', 'л':'l', 'м':'m', 'н':'n',
      'о':'o', 'п':'p', 'р':'r', 'с':'s', 'т':'t', 'у':'u', 'ф':'f', 'х':'h',
      'ц':'ts', 'ч':'ch', 'ш':'sh', 'щ':'shch', 'ъ':'', 'ы':'y', 'ь':'', 'э':'e',
      'ю':'yu', 'я':'ya'}
    return "".join([dic.get(c, c) for c in str(text).lower()])

def safe_slugify(text):
    return slugify(transliterate(text))

class Command(BaseCommand):
    help = 'Load products from supplier Excel file'

    def handle(self, *args, **kwargs):
        file_path = 'D:/Studies/Lab and pars/Web-ProgDJ(2)/DjangoWebProject1/export_universal_2026-06-16_1781596138_6a30ffea07f2a.xlsx'
        self.stdout.write('Чтение Excel файла...')
        df = pd.read_excel(file_path)
        
        target_categories = [
            "Электроинструменты BULL, MOLOT, WORTEX, ФИОЛЕНТ",
            "Садовая техника, оснастка и принадлежности",
            "Измерительный инструмент",
            "Хранение инструмента (ящики, сумки, пояса, тележки)",
            "Ручной инструмент",
            "Средства индивидуальной защиты и спецодежда",
            "Строительное оборудование"
        ]
        
        # Filter by main categories
        df_filtered = df[df['parentid_name1'].isin(target_categories)]
        
        # Фильтруем мусор (запчасти и узкоспециализированные товары)
        stop_words = [
            'в сборе', 'муфта', 'модуль', 'стартер', 'редуктор', 'фланец', 'грунтозацеп', 'удлинител', 
            'плуг', 'выкапывател', 'окучник', 'сцепка', 'культиватор', 'заглушка', 'пружина', 'шток', 
            'карбюратор', 'сальник', 'коленвал', 'подшипник', 'пробка',
            'лестниц', 'стремянк', 'ремень', 'ремни', 'декомпрессор', 'плиткорез', 'комплект крепежа', 
            'бетоносмесител', 'набор резцов', 'клупп', 'резьбонарез', 'таль', 'рукав', 'двигател', 
            'картофелесажал', 'подстолье', 'стол для', 'опора роликов', 'шланг', 'сопло', 'фильтр', 
            'верстак', 'губк', 'проволока', 'толкатель', 'гильза', 'поршнев', 'вал привод', 'ручка', 
            'кронштейн', 'чашка пусков', 'козлы', 'камер', 'гайк', 'контейнер', 'лента', 'валик', 
            'ключ', 'тиски', 'шоппер', 'органайзер', 'ведро', 'отвертк', 'клещи', 'бокорез', 
            'плоскогубц', 'головка ударн', 'головка торцев', 'держатель',
            'набор головок', 'маска бытов', 'трещотк', 'струбцин', 'плашк', 'метчик', 'тонкогубц',
            'сумка', 'кисть', 'кист', 'стамеск', 'гидроуров', 'ремкомплект', 'шнурок', 'надфил',
            'шпильковерт', 'набор отверток', 'маховик', 'барабан сцеплен', 'насос маслян', 
            'шестерня', 'напильник', 'натяжитель', 'прокладк', 'пружинный адаптер', 'набор-сет',
            'стеклорез', 'основание погружное', 'основание наклонное', 'платформа'
        ]
        
        df_filtered = df_filtered[~df_filtered['name'].str.lower().str.contains('|'.join(stop_words), na=False)]
        
        # Специальные правила:
        # Удаляем 'головка', но оставляем триммеры и мотокосы
        is_bad_head = df_filtered['name'].str.lower().str.contains('головка') & ~df_filtered['name'].str.lower().str.contains('триммер|мотокоса')
        df_filtered = df_filtered[~is_bad_head]

        # Удаляем 'ролик', но оставляем газонокосилки (если вдруг там есть ролики)
        is_bad_roller = df_filtered['name'].str.lower().str.contains('ролик')
        df_filtered = df_filtered[~is_bad_roller]

        # Удаляем 'ножниц', но оставляем садовые кусторезы
        is_bad_scissors = df_filtered['name'].str.lower().str.contains('ножниц') & ~df_filtered['name'].str.lower().str.contains('садовые|кусторез|аккум')
        df_filtered = df_filtered[~is_bad_scissors]

        # Удаляем 'звездочка', но оставляем леску
        is_bad_star = df_filtered['name'].str.lower().str.contains('звездочка') & ~df_filtered['name'].str.lower().str.contains('леска')
        df_filtered = df_filtered[~is_bad_star]
        
        self.stdout.write(f'Найдено {len(df_filtered)} товаров для загрузки.')
        
        # Словарь перевода характеристик
        prop_translation = {
            'prop_purpose': 'Назначение',
            'prop_warranty': 'Гарантия (мес)',
            'prop_shelf_life': 'Срок службы',
            'prop_length': 'Длина (м)',
            'prop_width': 'Ширина (м)',
            'prop_height': 'Высота (м)',
            'prop_weight_gross': 'Вес брутто (кг)',
            'prop_unit': 'Единица измерения',
            'prop_manufacturer': 'Производитель',
            'prop_importer': 'Импортер',
            'prop_tnved': 'Код ТН ВЭД'
        }
        
        # Словарь красивых названий главных категорий
        category_mapping = {
            "Электроинструменты BULL, MOLOT, WORTEX, ФИОЛЕНТ": "Электроинструмент",
            "Садовая техника, оснастка и принадлежности": "Садовая техника",
            "Хранение инструмента (ящики, сумки, пояса, тележки)": "Хранение инструмента",
            "Средства индивидуальной защиты и спецодежда": "Спецодежда и СИЗ"
        }
        
        for index, row in df_filtered.iterrows():
            try:
                # 1. БРЕНД
                brand_name = str(row['brand']).strip()
                if brand_name and brand_name != 'nan':
                    brand_slug = safe_slugify(brand_name) or f"brand-{index}"
                    brand, _ = Brand.objects.get_or_create(
                        name=brand_name,
                        defaults={'slug': brand_slug}
                    )
                else:
                    brand = None

                # 2. КАТЕГОРИЯ (Только 2 уровня: Главная -> Подкатегория)
                raw_cat1_name = str(row['parentid_name1']).strip()
                cat2_name = str(row['parentid_name2']).strip()
                
                # Делаем красивые названия
                cat1_name = category_mapping.get(raw_cat1_name, raw_cat1_name)
                
                parent_category = Category.objects.filter(name=cat1_name, parent__isnull=True).first()
                if not parent_category and cat1_name and cat1_name != 'nan':
                    slug = safe_slugify(cat1_name)
                    if Category.objects.filter(slug=slug).exists():
                        slug = f"{slug}-{index}"
                    parent_category = Category.objects.create(name=cat1_name, slug=slug)
                
                final_category = parent_category
                if cat2_name and cat2_name != 'nan':
                    final_category = Category.objects.filter(name=cat2_name, parent=parent_category).first()
                    if not final_category:
                        slug = safe_slugify(cat2_name)
                        if Category.objects.filter(slug=slug).exists():
                            slug = f"{slug}-{index}"
                        final_category = Category.objects.create(name=cat2_name, parent=parent_category, slug=slug)

                # 3. ТОВАР
                # Чистим цену
                price_str = str(row['price_recommended_shop']).replace(',', '.').replace(' ', '')
                try:
                    price = Decimal(price_str)
                except:
                    price = Decimal('0.00')

                sku = str(row['vendor_code']).strip()
                
                product, product_created = Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        'title': str(row['name']).strip()[:200],
                        'description': str(row['description']).strip() if str(row['description']) != 'nan' else '',
                        'price': price,
                        'quantity': 10, # Заглушка, так как остатков у поставщика нет
                        'brand': brand,
                        'category': final_category,
                    }
                )

                # 4. ФОТОГРАФИИ
                img_url = str(row['media_img']).strip()
                if img_url and img_url != 'nan' and product_created:
                    # Качаем только если товар только что создан, чтобы не дублировать фото
                    try:
                        response = requests.get(img_url, timeout=10)
                        if response.status_code == 200:
                            img_name = img_url.split('/')[-1]
                            product_img = ProductImage(product=product)
                            product_img.image.save(img_name, ContentFile(response.content), save=True)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Ошибка загрузки фото: {e}"))

                # 5. ХАРАКТЕРИСТИКИ
                prop_cols = [c for c in df.columns if c.startswith('prop_')]
                for col in prop_cols:
                    val = str(row[col]).strip()
                    if val and val != 'nan' and val != '0' and val != '0.0':
                        # Переводим на русский или оставляем как есть без префикса
                        char_name = prop_translation.get(col, col.replace('prop_', '').replace('_', ' ').capitalize())
                        char_obj, _ = Characteristic.objects.get_or_create(name=char_name)
                        ProductCharacteristic.objects.update_or_create(
                            product=product,
                            characteristic=char_obj,
                            defaults={'value': val[:255]}
                        )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Ошибка с товаром {row['vendor_code']}: {e}"))

        self.stdout.write(self.style.SUCCESS('ТЕСТОВАЯ ЗАГРУЗКА УСПЕШНО ЗАВЕРШЕНА!'))
