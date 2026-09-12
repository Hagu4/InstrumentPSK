from django.db import models
from django.db.models import Count, Q
import os
from django.contrib import admin, messages
from django.contrib.auth.models import User
from datetime import datetime
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.http import HttpResponseRedirect

class Category(models.Model):
    MAX_LEVEL = 3
    name = models.CharField(max_length=100, verbose_name="Название категории")
    slug = models.SlugField(unique=True, verbose_name="URL-псевдоним")
    description = models.TextField(blank=True, verbose_name="Описание категории")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Родительская категория")
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name="Изображение категории")
    icon = models.CharField(max_length=50, blank=True, help_text="Font Awesome icon class (например, 'fas fa-cog')", verbose_name="Иконка")
    color = models.CharField(max_length=7, blank=True, help_text="HEX-код цвета, например, #FF5733", verbose_name="Цвет иконки")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['parent__name', 'name']

    def __str__(self):
        return self.full_path

    def ancestor_chain(self):
        chain, seen_ids, seen_objects, node = [], set(), set(), self
        while node is not None:
            if id(node) in seen_objects or (node.pk and node.pk in seen_ids):
                raise ValidationError("Обнаружен цикл в дереве категорий.")
            seen_objects.add(id(node))
            if node.pk:
                seen_ids.add(node.pk)
            chain.append(node)
            node = node.parent
        return list(reversed(chain))

    @property
    def level(self):
        return len(self.ancestor_chain())

    @property
    def full_path(self):
        return " → ".join(category.name for category in self.ancestor_chain())

    def descendant_ids(self, include_self=False):
        result = [self.pk] if include_self else []
        frontier = [self.pk]
        while frontier:
            children = list(
                Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)
            )
            result.extend(children)
            frontier = children
        return result

    def clean(self):
        super().clean()
        parent = self.parent
        if parent is None:
            return

        seen_ids, seen_objects = set(), set()
        node = self
        depth = 0
        while node is not None:
            if id(node) in seen_objects or (node.pk and node.pk in seen_ids):
                raise ValidationError({"parent": "Родитель создаёт цикл в дереве категорий."})
            seen_objects.add(id(node))
            if node.pk:
                seen_ids.add(node.pk)
            depth += 1
            node = node.parent

        def subtree_height(category, visited):
            if not category.pk:
                return 1
            if category.pk in visited:
                raise ValidationError({"parent": "Родитель создаёт цикл в дереве категорий."})
            visited = visited | {category.pk}
            children = list(category.children.all())
            if not children:
                return 1
            return 1 + max(subtree_height(child, visited) for child in children)

        if depth + subtree_height(self, set()) - 1 > self.MAX_LEVEL:
            raise ValidationError({"parent": "Допускается не более трёх уровней категорий."})

    def get_absolute_url(self):
        return reverse('catalog_category', kwargs={'category_slug': self.slug})

    def get_total_products_count(self):
        return Product.objects.filter(category_id__in=self.descendant_ids(include_self=True)).count()

class Brand(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название бренда")
    slug = models.SlugField(unique=True, max_length=255, verbose_name="URL-псевдоним")
    image = models.ImageField(upload_to='brands/', blank=True, null=True, verbose_name="Логотип")
    color = models.CharField(max_length=7, blank=True, null=True, help_text="HEX-код цвета, например, #FF5733", verbose_name="Цвет бренда")

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('brand_detail', kwargs={'slug': self.slug})

class HeroCarouselSlide(models.Model):
    title = models.CharField(max_length=200, verbose_name="Заголовок слайда")
    subtitle = models.TextField(blank=True, verbose_name="Текст слайда")
    tag = models.CharField(max_length=50, blank=True, null=True, verbose_name="Маленький ярлык (напр. 'Акция', 'Новинка')")
    button_text = models.CharField(max_length=50, default="Подробнее", verbose_name="Текст кнопки")
    button_link = models.CharField(max_length=200, default="/catalog/", verbose_name="Ссылка кнопки")
    image = models.ImageField(upload_to='carousel/', blank=True, null=True, verbose_name="Изображение (опционально)")
    bg_gradient_start = models.CharField(max_length=7, default="#FF6B00", verbose_name="Начало градиента (HEX)")
    bg_gradient_end = models.CharField(max_length=7, default="#FF9500", verbose_name="Конец градиента (HEX)")
    text_color = models.CharField(max_length=7, default="#FFFFFF", verbose_name="Цвет текста (HEX)")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        verbose_name = "Слайд карусели"
        verbose_name_plural = "Слайды карусели"
        ordering = ['order', '-id']

    def __str__(self):
        return self.title

class Promotion(models.Model):
    title = models.CharField(max_length=200, verbose_name="Заголовок акции")
    subtitle = models.CharField(max_length=200, blank=True, verbose_name="Подзаголовок")
    description = models.TextField(blank=True, verbose_name="Описание")
    discount = models.PositiveIntegerField(default=0, verbose_name="Скидка (%)")
    link = models.CharField(max_length=200, blank=True, verbose_name="Ссылка (URL или имя маршрута)")
    link_text = models.CharField(max_length=50, default="Подробнее", verbose_name="Текст кнопки")
    icon = models.CharField(max_length=50, default="fas fa-percent", verbose_name="Иконка (Font Awesome)")
    color = models.CharField(max_length=7, default="#FF6B35", verbose_name="Цвет фона (HEX)")
    image = models.ImageField(upload_to='promotions/', blank=True, null=True, verbose_name="Фоновое изображение")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    is_permanent = models.BooleanField(default=False, verbose_name="Постоянная акция")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата окончания")
    order = models.PositiveIntegerField(default=0, verbose_name="Порядок отображения")
    show_on_home = models.BooleanField(default=True, verbose_name="Показывать на главной")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        if self.link:
            if self.link.startswith('/'):
                return self.link
            return reverse(self.link, kwargs={})
        return reverse('news')

    def is_valid(self):
        from django.utils import timezone
        if not self.is_active: return False
        if self.is_permanent: return True
        if self.end_date: return self.end_date > timezone.now()
        return True

    def days_remaining(self):
        from django.utils import timezone
        if self.is_permanent or not self.end_date: return None
        remaining = self.end_date - timezone.now()
        return max(0, remaining.days)

class Product(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название товара")
    sku = models.CharField(max_length=100, unique=True, verbose_name="Артикул (SKU)", null=True, blank=True)
    description = models.TextField(verbose_name="Описание", blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True, verbose_name="Цена")
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Старая цена (без скидки)')
    quantity = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Количество на складе")
    added_date = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Дата добавления")
    author = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Автор")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Категория")
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name="Бренд")
    purchase_count = models.PositiveIntegerField(default=0, db_index=True, verbose_name="Количество покупок")
    package_contents = models.TextField(blank=True, null=True, verbose_name="Комплектация")

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['-added_date']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('product_detail', args=[str(self.id)])

    @property
    def is_new(self):
        from django.utils import timezone
        return (timezone.now() - self.added_date).days < 7

    @property
    def discount_percentage(self):
        if self.old_price and self.old_price > self.price:
            return int(((self.old_price - self.price) / self.old_price) * 100)
        return 0

    @property
    def get_specs_line(self):
        key_specs = self.characteristics.all()[:3]
        if not key_specs:
            if self.description: return ' '.join(self.description.split()[:10]) + '...'
            return ''
        return ' · '.join([f"{spec.characteristic.name}: {spec.value}" for spec in key_specs])

    @property
    def average_rating(self):
        from django.db.models import Avg
        result = self.reviews.aggregate(avg=Avg('rating'))
        return result['avg'] or 0

    @property
    def reviews_count(self):
        return self.reviews.count()

import uuid

def get_product_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('products/', filename)

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE, verbose_name="Товар")
    image = models.ImageField(upload_to=get_product_image_path, verbose_name="Изображение")

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товара"

    def __str__(self):
        return f"Изображение для {self.product.title}"

class Characteristic(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Название характеристики")

    class Meta:
        verbose_name = "Характеристика"
        verbose_name_plural = "Характеристики"
        ordering = ['name']

    def __str__(self):
        return self.name

class ProductCharacteristic(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='characteristics', verbose_name="Товар")
    characteristic = models.ForeignKey(Characteristic, on_delete=models.PROTECT, verbose_name="Характеристика")
    value = models.CharField(max_length=255, verbose_name="Значение")

    class Meta:
        verbose_name = "Характеристика товара"
        verbose_name_plural = "Характеристики товара"
        unique_together = ('product', 'characteristic')

    def __str__(self):
        return f'{self.characteristic.name}: {self.value}'

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name="Товар")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Автор")
    text = models.TextField(verbose_name="Текст отзыва")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Рейтинг")
    date = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    pros = models.TextField(verbose_name="Достоинства", blank=True, default='')
    cons = models.TextField(verbose_name="Недостатки", blank=True, default='')
    video_url = models.URLField(verbose_name="Ссылка на видео", blank=True, default='')
    helpful_count = models.IntegerField(verbose_name="Полезно", default=0)
    not_helpful_count = models.IntegerField(verbose_name="Не полезно", default=0)

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ['-date']

    def __str__(self):
        return f'Отзыв от {self.author} на {self.product.title}'

class ReviewVote(models.Model):
    VOTE_CHOICES = [('helpful', 'Полезно'), ('not_helpful', 'Не полезно')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='votes', verbose_name="Отзыв")
    vote_type = models.CharField(max_length=20, choices=VOTE_CHOICES, verbose_name="Тип голоса")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата голоса")

    class Meta:
        verbose_name = "Голос за отзыв"
        verbose_name_plural = "Голоса за отзывы"
        unique_together = ('user', 'review')

    def __str__(self):
        return f'{self.user.username} - {self.vote_type} - {self.review.id}'

class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='reviews/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Order(models.Model):
    STATUS_CHOICES = [
        ('CART', 'В корзине'),
        ('CREATED', 'Оформлен'),
        ('ASSEMBLING', 'В сборке'),
        ('READY_FOR_PICKUP', 'Готов к выдаче'),
        ('COMPLETED', 'Выдан и оплачен'),
        ('CANCELLED', 'Отменен'),
    ]
    DELIVERY_CHOICES = [('PICKUP', 'Самовывоз'), ('DELIVERY_POINT', 'Доставка в пункт выдачи'), ('HOME_DELIVERY', 'Доставка на дом')]
    PAYMENT_CHOICES = [('CARD_ONLINE', 'Картой онлайн'), ('CARD_ON_DELIVERY', 'Картой при получении'), ('CASH_ON_DELIVERY', 'Наличными при получении')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CART', verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    order_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата оформления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Общая сумма")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата оплаты")
    cancelled_by_user = models.BooleanField(default=False, verbose_name="Отменен пользователем")
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES, null=True, blank=True, verbose_name="Способ доставки")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, null=True, blank=True, verbose_name="Способ оплаты")
    delivery_address = models.TextField(null=True, blank=True, verbose_name="Адрес доставки")
    pickup_point = models.CharField(max_length=255, null=True, blank=True, verbose_name="Пункт выдачи")
    is_stock_reduced = models.BooleanField(default=False, verbose_name="Склад обновлен")

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-order_date', '-created_at']

    def __str__(self):
        return f"Заказ {self.id} от {self.user.username} ({self.get_status_display()})"

    def get_subtotal(self):
        return sum(item.get_cost() for item in self.items.all())

    def get_delivery_cost(self):
        costs = {'PICKUP': Decimal('0.00'), 'DELIVERY_POINT': Decimal('150.00'), 'HOME_DELIVERY': Decimal('350.00')}
        return costs.get(self.delivery_method, Decimal('0.00'))

    def get_absolute_url(self):
        return reverse('order_detail', kwargs={'pk': self.pk})

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE, verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    is_preorder = models.BooleanField(default=False, verbose_name="Под заказ")

    class Meta:
        verbose_name = "Элемент заказа"
        verbose_name_plural = "Элементы заказа"

    def __str__(self):
        return f"{self.quantity} x {self.product.title} в заказе {self.order.id}"

    def get_cost(self):
        return self.quantity * self.product.price

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    phone_number = models.CharField(max_length=20, blank=True, verbose_name="Номер телефона")
    city = models.CharField(max_length=100, blank=True, verbose_name="Город")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")

    class Meta:
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self):
        return f'Профиль пользователя {self.user.username}'

class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites', verbose_name="Пользователь")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by', verbose_name="Товар")
    added_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранные товары"
        unique_together = ('user', 'product')
        ordering = ['-added_date']

class RepairRequest(models.Model):
    STATUS_CHOICES = [('NEW', '🔴 Новая'), ('DIAGNOSING', '🟡 Диагностика'), ('IN_PROGRESS', '🔵 В работе'), ('READY', '🟢 Готов'), ('COMPLETED', '⚫ Выдан')]
    name = models.CharField(max_length=100, verbose_name="Имя клиента")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(verbose_name="Email")
    tool_type = models.CharField(max_length=200, verbose_name="Тип инструмента")
    description = models.TextField(verbose_name="Описание поломки")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW', verbose_name="Статус")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    request_number = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Номер заявки")

    class Meta:
        verbose_name = "Заявка на ремонт"
        verbose_name_plural = "Заявки на ремонт"
        ordering = ['-created_at']

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=Order)
def update_stock_and_stats(sender, instance, **kwargs):
    if instance.status == 'COMPLETED' and not instance.is_stock_reduced:
        for item in instance.items.all():
            Product.objects.filter(id=item.product_id).update(
                quantity=models.F('quantity') - item.quantity,
                purchase_count=models.F('purchase_count') + item.quantity
            )
        Order.objects.filter(id=instance.id).update(is_stock_reduced=True)
    elif instance.status == 'CANCELLED' and instance.is_stock_reduced:
        for item in instance.items.all():
            Product.objects.filter(id=item.product_id).update(
                quantity=models.F('quantity') + item.quantity,
                purchase_count=models.F('purchase_count') - item.quantity
            )
        Order.objects.filter(id=instance.id).update(is_stock_reduced=False)

class Feedback(models.Model):
    RATING_CHOICES = [(1, '1 звезда'), (2, '2 звезды'), (3, '3 звезды'), (4, '4 звезды'), (5, '5 звезд')]
    USABILITY_CHOICES = [('очень_удобный', 'Очень удобный'), ('удобный', 'Удобный'), ('неудобный', 'Неудобный'), ('очень_неудобный', 'Очень неудобный')]
    FREQUENCY_CHOICES = [('ежедневно', 'Ежедневно'), ('несколько_раз_в_неделю', 'Несколько раз в неделю'), ('раз_в_неделю', 'Раз в неделю'), ('редко', 'Редко'), ('впервые', 'Впервые')]
    name = models.CharField(max_length=100, verbose_name='Ваше имя')
    email = models.EmailField(verbose_name='Email')
    overall_rating = models.IntegerField(default=0, choices=RATING_CHOICES, verbose_name='Общая оценка')
    usability_rating = models.CharField(max_length=20, choices=USABILITY_CHOICES, verbose_name='Удобство сайта', default='удобный')
    visit_frequency = models.CharField(max_length=30, choices=FREQUENCY_CHOICES, verbose_name='Частота посещений', default='редко')
    comments = models.TextField(verbose_name='Комментарии', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Обратная связь"
        verbose_name_plural = "Обратная связь"
        ordering = ['-created_at']

class News(models.Model):
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="URL-псевдоним")
    short_description = models.CharField(max_length=300, blank=True, verbose_name="Краткое описание")
    content = models.TextField(verbose_name="Содержание статьи")
    image = models.ImageField(upload_to='news/', blank=True, null=True, verbose_name="Изображение")
    is_published = models.BooleanField(default=True, verbose_name="Опубликовано")
    is_featured = models.BooleanField(default=False, verbose_name="Рекомендуемая")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Автор")

    class Meta:
        verbose_name = "Новость"
        verbose_name_plural = "Новости"
        ordering = ['-created_at']

    def get_absolute_url(self):
        return reverse('news_detail', kwargs={'slug': self.slug})

class ProductCharacteristicInline(admin.TabularInline):
    model = ProductCharacteristic
    extra = 1
    autocomplete_fields = ['characteristic']

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'title', 'brand', 'price', 'quantity', 'added_date', 'category')
    list_filter = ('added_date', 'category', 'brand')
    search_fields = ('title', 'description', 'sku')
    autocomplete_fields = ['category', 'brand']
    inlines = [ProductCharacteristicInline, ProductImageInline]

@admin.register(Characteristic)
class CharacteristicAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(ProductCharacteristic)
class ProductCharacteristicAdmin(admin.ModelAdmin):
    list_display = ('product', 'characteristic', 'value')
    list_filter = ('characteristic',)
    search_fields = ('product__title', 'characteristic__name', 'value')

class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 1
    readonly_fields = ('uploaded_at',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'author', 'rating', 'date')
    list_filter = ('date', 'rating')
    search_fields = ('text', 'author__username')
    autocomplete_fields = ['product', 'author']
    inlines = [ReviewImageInline]

class CategoryLevelFilter(admin.SimpleListFilter):
    title = "Уровень"
    parameter_name = "level"

    def lookups(self, request, model_admin):
        return (
            ("1", "Первый"),
            ("2", "Второй"),
            ("3", "Третий"),
        )

    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.filter(parent__isnull=True)
        if self.value() == "2":
            return queryset.filter(
                parent__isnull=False,
                parent__parent__isnull=True,
            )
        if self.value() == "3":
            return queryset.filter(parent__parent__isnull=False)
        return queryset


class CategoryRootFilter(admin.SimpleListFilter):
    title = "Корневая категория"
    parameter_name = "root"

    def lookups(self, request, model_admin):
        return Category.objects.filter(parent__isnull=True).values_list(
            "pk", "name"
        )

    def queryset(self, request, queryset):
        root_id = self.value()
        if root_id is None:
            return queryset
        return queryset.filter(
            Q(pk=root_id)
            | Q(parent_id=root_id)
            | Q(parent__parent_id=root_id)
        ).distinct()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "full_path_display",
        "level_display",
        "parent",
        "own_product_count",
        "branch_product_count",
        "slug",
        "add_child_link",
    )
    list_filter = (CategoryLevelFilter, CategoryRootFilter)
    search_fields = ("name", "slug", "parent__name", "parent__parent__name")
    list_select_related = ("parent", "parent__parent")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            own_products=Count("product", distinct=True),
            child_products=Count("children__product", distinct=True),
            grandchild_products=Count(
                "children__children__product", distinct=True
            ),
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        category = self.get_object(request, object_id)
        if category and self.has_delete_permission(request, category) and (
            category.children.exists() or category.product_set.exists()
        ):
            self.message_user(
                request,
                "Нельзя удалить категорию, пока в ней есть товары или дочерние категории. "
                "Сначала перенесите товары и удалите дочерние категории.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse("admin:app_category_change", args=[category.pk])
            )
        return super().delete_view(request, object_id, extra_context)

    @admin.display(description="Полный путь")
    def full_path_display(self, obj):
        return obj.full_path

    @admin.display(description="Уровень")
    def level_display(self, obj):
        return obj.level

    @admin.display(description="Товаров в категории", ordering="own_products")
    def own_product_count(self, obj):
        return obj.own_products

    @admin.display(description="Товаров в ветке")
    def branch_product_count(self, obj):
        return obj.own_products + obj.child_products + obj.grandchild_products

    @admin.display(description="Добавление")
    def add_child_link(self, obj):
        if obj.level >= Category.MAX_LEVEL:
            return ""
        label = (
            "Добавить подкатегорию"
            if obj.level == 1
            else "Добавить подподкатегорию"
        )
        return format_html(
            '<a href="{}?parent={}">{}</a>',
            reverse("admin:app_category_add"),
            obj.pk,
            label,
        )

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'color')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'created_at', 'total_price', 'is_stock_reduced')
    list_filter = ('status', 'created_at', 'is_stock_reduced')
    search_fields = ('user__username', 'id')

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number')

@admin.register(RepairRequest)
class RepairRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'tool_type', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    list_editable = ('status',)

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'added_date')

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'overall_rating', 'created_at')

@admin.register(HeroCarouselSlide)
class HeroCarouselSlideAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'order')
    list_editable = ('is_active', 'order')

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('title', 'discount', 'is_active', 'order')
    list_editable = ('is_active', 'order')

class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Код промокода")
    discount_percent = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_uses = models.PositiveIntegerField(default=0)
    used_count = models.PositiveIntegerField(default=0, editable=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self, order_amount=0):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active: return False, "Промокод неактивен"
        if self.valid_from and now < self.valid_from: return False, "Промокод ещё не действует"
        if self.valid_until and now > self.valid_until: return False, "Срок действия промокода истёк"
        if self.max_uses > 0 and self.used_count >= self.max_uses: return False, "Лимит использований исчерпан"
        if self.min_order_amount > 0 and order_amount < self.min_order_amount: return False, f"Мин. сумма: {self.min_order_amount}"
        return True, ""

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_active', 'used_count')
