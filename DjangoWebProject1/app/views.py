from decimal import Decimal
from datetime import datetime, timedelta
import pickle
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib.auth import authenticate, login
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from transliterate import slugify as transliterate_slugify
from .models import Product, Review, Category, Order, OrderItem, Profile, ProductCharacteristic, Feedback, Favorite, RepairRequest, Brand, ProductImage, Promotion, News, PromoCode, ReviewImage, ReviewVote
from .forms import BootstrapAuthenticationForm, ProductForm, ReviewForm, FeedbackForm, ProfileForm, BootstrapUserCreationForm, ExtendedRegistrationForm, DeliveryMethodForm, DeliveryAddressForm, PaymentMethodForm, ProductCharacteristicFormSet
from django.db import models
from django.db.models import Q, Avg, Sum, Case, When, Count, Min, Max, Prefetch
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML
from django.templatetags.static import static # Added for quick view image fallback
from django.core.cache import cache

def invalidate_product_cache(product_id):
    """
    Invalidate cache for a specific product
    """
    # Invalidate the quick view cache
    cache_key = f'product_quick_view_{product_id}'
    cache.delete(cache_key)
    
    # Invalidate other related caches if needed
    # cache.delete_pattern(f'product_detail_{product_id}*')
    # cache.delete_pattern(f'catalog_*')

def invalidate_catalog_cache():
    """
    Invalidate catalog cache
    """
    cache.delete_pattern('catalog_*')
    cache.delete_pattern('product_quick_view_*')

def switch_layout(text):
    if not text: return text
    layout = dict(zip(
        map(ord, "qwertyuiop[]asdfghjkl;'zxcvbnm,./`"
                 "QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?~"),
        "йцукенгшщзхъфывапролджэячсмитьбю.ё"
        "ЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,Ё"
    ))
    return text.translate(layout)

@login_required
def download_order_check_pdf(request, order_id):
    """
    Generates and serves a PDF receipt for a given order.
    """
    # Fetch the order, ensuring it belongs to the current user or the user is a manager
    order = get_object_or_404(Order, id=order_id)
    if not (request.user.is_staff or order.user == request.user):
        return HttpResponseForbidden("У вас нет доступа к этому заказу.")

    # Render the HTML template with order context
    html_string = render_to_string('app/pdf/order_check.html', {'order': order})

    # Create a PDF file from the HTML string
    html = HTML(string=html_string)
    pdf_file = html.write_pdf()

    # Create an HTTP response with the PDF
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="order_{order.id}_check.pdf"'
    
    return response


def live_search(request):
    query = request.GET.get('q', '')
    products_data = []
    if query:
        switched_query = switch_layout(query)
        # Build a complex Q object for searching across multiple fields
        search_filter = (
            Q(title__icontains=query) |
            Q(title__icontains=switched_query) |
            Q(sku__icontains=query) |
            Q(sku__icontains=switched_query) |
            Q(description__icontains=query) |
            Q(description__icontains=switched_query) |
            Q(category__name__icontains=query) |
            Q(category__name__icontains=switched_query) |
            Q(category__parent__name__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(characteristics__characteristic__name__icontains=query) |
            Q(characteristics__value__icontains=query) |
            Q(characteristics__value__icontains=switched_query)
        )
        
        products = Product.objects.filter(search_filter).select_related(
            'category', 'brand'
        ).prefetch_related('images', 'characteristics').distinct()[:10]
        
        for product in products:
            first_image = product.images.first()
            
            # Находим совпавшую характеристику для подсветки
            matched_chars = []
            for char in product.characteristics.all():
                if query.lower() in char.characteristic.name.lower() or query.lower() in char.value.lower():
                    matched_chars.append(f"{char.characteristic.name}: {char.value}")
            
            products_data.append({
                'id': product.id,
                'name': product.title,
                'url': product.get_absolute_url(),
                'category': product.category.name if product.category else '',
                'image_url': first_image.image.url if first_image else '',
                'brand': product.brand.name if product.brand else '',
                'sku': product.sku,
                'matched_chars': matched_chars[:2]  # Показываем до 2 совпавших характеристик
            })
            
    return JsonResponse(products_data, safe=False)

@login_required
def profile_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = None
    
    context = {
        'title': 'Мой профиль',
        'profile': profile
    }
    return render(request, 'app/profile.html', context)

@login_required
@require_POST
def toggle_favorite(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    favorite, created = Favorite.objects.get_or_create(user=request.user, product=product)

    if not created:
        favorite.delete()
        is_favorited = False
    else:
        is_favorited = True

    # You can also return the count of favorites if needed on the frontend
    favorites_count = Favorite.objects.filter(user=request.user).count()

    return JsonResponse({'status': 'success', 'is_favorited': is_favorited, 'favorites_count': favorites_count})

@login_required
def favorites_view(request):
    favorite_products = Product.objects.filter(favorited_by__user=request.user).prefetch_related('images')
    
    # Pass the list of favorite product IDs to the template
    # This helps in setting the initial state of the favorite buttons
    favorite_product_ids = list(favorite_products.values_list('id', flat=True))

    context = {
        'title': 'Избранные товары',
        'products': favorite_products,
        'favorite_product_ids': favorite_product_ids,
    }
    return render(request, 'app/favorites.html', context)



def is_manager(user):
    return user.is_authenticated and (user.groups.filter(name='Менеджер').exists() or user.is_superuser)

# --- Страница "Корзина" ---
@login_required
def cart(request):
    # Поддержка AJAX запросов
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        order, created = Order.objects.get_or_create(user=request.user, status='CART')
        
        if request.method == 'POST':
            item_id = None
            # Обработка изменения количества
            for key, value in request.POST.items():
                if key.startswith('quantity_'):
                    item_id = key.replace('quantity_', '')
                    try:
                        item = OrderItem.objects.get(id=item_id, order=order)
                        new_quantity = int(int(value))
                        # Allow pre-order if quantity is 0
                        if item.product.quantity > 0 and new_quantity > item.product.quantity:
                            new_quantity = item.product.quantity
                        
                        if new_quantity > 0:
                            item.quantity = new_quantity
                            item.save()
                        else:
                            item.delete()
                    except OrderItem.DoesNotExist:
                        pass
                
                # Обработка удаления
                elif key.startswith('delete_'):
                    item_id = key.replace('delete_', '')
                    try:
                        item = OrderItem.objects.get(id=item_id, order=order)
                        item.delete()
                    except OrderItem.DoesNotExist:
                        pass
            
            # Пересчитываем итоги
            order_items = OrderItem.objects.filter(order=order)
            total_cost = sum(item.get_cost() for item in order_items)
            order.total_price = total_cost
            order.save()
            
            # Получаем стоимость конкретного товара для ответа
            item_total = 0
            if item_id:
                try:
                    item = OrderItem.objects.get(id=item_id, order=order)
                    item_total = float(item.get_cost())
                except OrderItem.DoesNotExist:
                    pass
            
            # Возвращаем JSON ответ для AJAX
            from django.http import JsonResponse
            
            # Get the updated quantity for the specific item
            current_item_quantity = 0
            if item_id:
                try:
                    item = OrderItem.objects.get(id=item_id)
                    current_item_quantity = item.quantity
                except OrderItem.DoesNotExist:
                    pass

            total_quantity = OrderItem.objects.filter(order=order).aggregate(Sum('quantity'))['quantity__sum']
            
            promo_discount = request.session.get('promo_discount', 0)
            
            return JsonResponse({
                'success': True,
                'total_cost': float(total_cost),
                'item_total': item_total,
                'total_quantity': total_quantity if total_quantity is not None else 0,
                'quantity': current_item_quantity,
                'promo_discount': promo_discount,
            })
    
    # Стандартная обработка (без AJAX)
    order, created = Order.objects.get_or_create(user=request.user, status='CART')
    order_items = OrderItem.objects.filter(order=order).select_related('product').prefetch_related('product__images')
    
    # Manually attach the first image URL to each item for robust access in the template
    for item in order_items:
        first_image = item.product.images.first()
        item.first_image_url = first_image.image.url if first_image else None

    total_cost = sum(item.get_cost() for item in order_items)

    if request.method == 'POST':
        # Обработка изменения количества или удаления
        for item in order_items:
            new_quantity = request.POST.get(f'quantity_{item.id}')
            if new_quantity:
                try:
                    new_quantity = int(new_quantity)
                    if new_quantity > item.product.quantity:
                        new_quantity = item.product.quantity
                    
                    if new_quantity > 0:
                        item.quantity = new_quantity
                        item.save()
                    else:
                        item.delete()
                except ValueError:
                    pass
            if request.POST.get(f'delete_{item.id}'):
                item.delete()

        order_items = OrderItem.objects.filter(order=order)
        total_cost = sum(item.get_cost() for item in order_items)
        order.total_price = total_cost
        order.save()

        return redirect('cart')

    recently_viewed_products = []
    if not order_items.exists():
        recently_viewed_ids = request.session.get('recently_viewed', [])
        if recently_viewed_ids:
            preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(recently_viewed_ids)])
            recently_viewed_products = Product.objects.filter(id__in=recently_viewed_ids).order_by(preserved_order).prefetch_related('images')

    return render(request, 'app/cart.html', {
        'title': 'Корзина',
        'order': order,
        'order_items': order_items,
        'total_cost': total_cost,
        'recently_viewed_products': recently_viewed_products,
    })


@login_required
def checkout(request):
    order = get_object_or_404(Order, user=request.user, status='CART')
    order_items = OrderItem.objects.filter(order=order).select_related('product').prefetch_related('product__images')
    
    if not order_items.exists():
        return redirect('cart')
    
    step = int(request.GET.get('step', 1))
    if step < 1:
        step = 1
    if step > 3:
        step = 3
    
    delivery_method = request.session.get('delivery_method', 'PICKUP')
    payment_method = request.session.get('payment_method', 'CARD_ONLINE')
    delivery_address = request.session.get('delivery_address', {})
    
    profile = getattr(request.user, 'profile', None)
    contact_info = {
        'name': request.user.get_full_name() or '',
        'phone': getattr(profile, 'phone_number', '') or '',
        'email': request.user.email or '',
    }
    
    if request.method == 'POST':
        # Get step from POST hidden field, fallback to GET
        step = int(request.POST.get('step', request.GET.get('step', 1)))
        
        if 'next' in request.POST:
            if step == 1:
                delivery_method = request.POST.get('delivery_method', 'PICKUP')
                request.session['delivery_method'] = delivery_method
                
                delivery_address = {
                    'city': request.POST.get('city', ''),
                    'street': request.POST.get('street', ''),
                    'house': request.POST.get('house', ''),
                    'apartment': request.POST.get('apartment', ''),
                }
                request.session['delivery_address'] = delivery_address
                
                # Check payment method - if not CARD_ONLINE, skip payment step
                # But for now, we'll always go to step 2 to confirm
                step = 2
                
            elif step == 2:
                payment_method = request.POST.get('payment_method', 'CARD_ONLINE')
                request.session['payment_method'] = payment_method
                step = 3
                
        elif 'confirm' in request.POST:
            delivery_method = 'PICKUP'
            payment_method = request.POST.get('payment_method', 'CARD_ON_DELIVERY')
            
            subtotal = sum(item.get_cost() for item in order_items)
            delivery_cost = 0
            
            promo_discount = request.session.get('promo_discount', 0)
            total_price = subtotal + delivery_cost - promo_discount
            
            # Mark items as pre-order if they are out of stock
            for item in order_items:
                if item.product.quantity <= 0:
                    item.is_preorder = True
                    item.save()
            
            order.order_date = timezone.now()
            order.status = 'CREATED'
            order.delivery_method = delivery_method
            order.payment_method = payment_method
            order.delivery_address = "Самовывоз из магазина: г. Псков, ул. Звездная, д.3"
            order.contact_phone = request.POST.get('contact_phone', contact_info['phone'])
            order.total_price = total_price
            order.save()
            
            request.session.pop('promo_code', None)
            request.session.pop('promo_discount', None)
            request.session.pop('delivery_method', None)
            request.session.pop('delivery_address', None)
            request.session.pop('payment_method', None)
            
            return redirect('order_complete')
    
    subtotal = sum(item.get_cost() for item in order_items)
    # Force single page step 3 layout, delivery is always pickup
    step = 3
    delivery_cost = 0
    delivery_method = 'PICKUP'
    
    promo_discount = request.session.get('promo_discount', 0)
    total_price = subtotal + delivery_cost - promo_discount
    
    return render(request, 'app/checkout.html', {
        'title': 'Оформление заказа',
        'order': order,
        'order_items': order_items,
        'step': step,
        'subtotal': subtotal,
        'delivery_cost': delivery_cost,
        'promo_discount': promo_discount,
        'total_price': total_price,
        'delivery_method': delivery_method,
        'payment_method': payment_method,
        'delivery_address': delivery_address,
        'contact_info': contact_info,
    })


@login_required
@require_POST
def apply_promo_code(request):
    promo_code = request.POST.get('promo_code', '').strip().upper()
    
    if not promo_code:
        return JsonResponse({'success': False, 'error': 'Введите промокод'})
    
    try:
        promo = PromoCode.objects.get(code=promo_code)
        order = Order.objects.get(user=request.user, status='CART')
        order_items = OrderItem.objects.filter(order=order)
        total_cost = sum(item.get_cost() for item in order_items)
        
        is_valid, error_message = promo.is_valid(total_cost)
        
        if not is_valid:
            return JsonResponse({'success': False, 'error': error_message})
        
        discount = promo.calculate_discount(total_cost)
        new_total = total_cost - discount
        
        request.session['promo_code'] = promo.code
        request.session['promo_discount'] = float(discount)
        
        return JsonResponse({
            'success': True,
            'discount': float(discount),
            'new_total': float(new_total),
            'promo_code': promo.code,
            'discount_percent': promo.discount_percent if promo.discount_percent else None,
        })
        
    except PromoCode.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Промокод не найден'})


@login_required
@require_POST
def remove_promo_code(request):
    if 'promo_code' in request.session:
        del request.session['promo_code']
    if 'promo_discount' in request.session:
        del request.session['promo_discount']
    
    return JsonResponse({'success': True})
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Sum, Case, When, Count, Min, Max

def get_category_breadcrumbs(category):
    breadcrumbs = []
    current = category
    while current:
        breadcrumbs.insert(0, current)
        current = current.parent
    return breadcrumbs

def catalog(request, category_slug=None):
    if request.method == 'POST' and 'product_id' in request.POST:
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))

        if request.user.is_authenticated:
            product = get_object_or_404(Product, id=product_id)
            cart_order, created = Order.objects.get_or_create(
                user=request.user, 
                status='CART'
            )
            
            cart_item, created = OrderItem.objects.get_or_create(
                order=cart_order,
                product=product,
                defaults={'quantity': 0}
            )

            new_quantity = cart_item.quantity + quantity
            if product.quantity > 0 and new_quantity > product.quantity:
                new_quantity = product.quantity
            
            if new_quantity > 0:
                cart_item.quantity = new_quantity
                cart_item.save()
            else:
                cart_item.delete()

            return redirect('cart')
        else:
            return redirect('login')

    products_list = Product.objects.filter(category__isnull=False).select_related('brand', 'category').prefetch_related('images', 'reviews').order_by('-id')
    
    current_category = None
    current_category_children = []
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        category_ids = current_category.descendant_ids(include_self=True)
        products_list = products_list.filter(category_id__in=category_ids)

    query = request.GET.get('q')
    if query:
        switched_query = switch_layout(query)
        products_list = products_list.filter(
            Q(title__icontains=query) |
            Q(title__icontains=switched_query) |
            Q(description__icontains=query) |
            Q(description__icontains=switched_query) |
            Q(characteristics__characteristic__name__icontains=query) |
            Q(characteristics__value__icontains=query) |
            Q(characteristics__value__icontains=switched_query) |
            Q(category__name__icontains=query) |
            Q(category__name__icontains=switched_query)
        ).distinct()

    # Get the price range for the slider *before* applying the price filter from GET params
    price_range = products_list.aggregate(
        min_val=Min('price'),
        max_val=Max('price')
    )
    price_range_min = int(price_range['min_val'] or 0)
    price_range_max = int(price_range['max_val'] or 100000) # Default max if no products

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price and min_price.isdigit():
        products_list = products_list.filter(price__gte=min_price)
    if max_price and max_price.isdigit():
        products_list = products_list.filter(price__lte=max_price)

    availability_options = request.GET.getlist('availability')
    if 'in_stock' in availability_options and 'on_order' not in availability_options:
        products_list = products_list.filter(quantity__gt=0)
    elif 'on_order' in availability_options and 'in_stock' not in availability_options:
        products_list = products_list.filter(quantity=0)

    # Получаем бренды и их количество ДО применения фильтра по брендам
    # MODIFIED: Include brand__color in values()
    brands_with_counts = products_list.filter(brand__isnull=False).values('brand__name', 'brand__slug', 'brand__color').annotate(count=Count('id', distinct=True)).order_by('-count')

    selected_brands_slugs = request.GET.getlist('brand') # Renamed to avoid confusion
    if selected_brands_slugs:
        products_list = products_list.filter(brand__slug__in=selected_brands_slugs)
        # MODIFIED: Fetch full Brand objects for selected brands
        selected_brand_objects = Brand.objects.filter(slug__in=selected_brands_slugs)
    else:
        selected_brand_objects = []

    # Sorting
    sort_by = request.GET.get('sort_by', 'popularity')
    if sort_by == 'popularity':
        # Сортировка по реальным продажам из OrderItem
        products_list = products_list.annotate(
            total_sold=Sum('orderitem__quantity', filter=Q(orderitem__order__status__in=['PAID', 'ASSEMBLING', 'SHIPPED', 'DELIVERING', 'AWAITING_PICKUP', 'ARRIVED', 'COMPLETED']))
        ).order_by('-total_sold', '-added_date')
    elif sort_by == 'price_asc':
        products_list = products_list.order_by('price')
    elif sort_by == 'price_desc':
        products_list = products_list.order_by('-price')
    elif sort_by == 'newest':
        products_list = products_list.order_by('-added_date')

    paginator = Paginator(products_list, 21)  # Show 21 products per page (divisible by 3).
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)

    # Set is_hit attribute on products (top 3 by actual sales from OrderItem)
    top_products_by_sales = OrderItem.objects.filter(
        order__status__in=['AWAITING_PAYMENT', 'PAID', 'ASSEMBLING', 'SHIPPED', 'DELIVERING', 'AWAITING_PICKUP', 'ARRIVED', 'COMPLETED']
    ).values('product__id').annotate(
        total_sold=Sum('quantity')
    ).order_by('-total_sold')[:3]
    
    top_product_ids = [item['product__id'] for item in top_products_by_sales]
    
    for product in products.object_list:
        product.is_hit = product.id in top_product_ids


    leaf_categories = Category.objects.annotate(
        catalog_product_count=Count('product', distinct=True),
    )
    child_categories = Category.objects.annotate(
        catalog_product_count=(
            Count('product', distinct=True)
            + Count('children__product', distinct=True)
        ),
    ).prefetch_related(
        Prefetch('children', queryset=leaf_categories),
    )
    top_level_categories = list(
        Category.objects.filter(parent__isnull=True).annotate(
            catalog_product_count=(
                Count('product', distinct=True)
                + Count('children__product', distinct=True)
                + Count('children__children__product', distinct=True)
            ),
        ).prefetch_related(
            Prefetch('children', queryset=child_categories),
        )
    )

    category_tree_by_id = {}
    for root_category in top_level_categories:
        category_tree_by_id[root_category.pk] = root_category
        for child_category in root_category.children.all():
            category_tree_by_id[child_category.pk] = child_category
            for leaf_category in child_category.children.all():
                category_tree_by_id[leaf_category.pk] = leaf_category

    if current_category:
        current_category = category_tree_by_id[current_category.pk]
        current_category_children = [
            child
            for child in current_category.children.all()
        ]
        current_category_children.sort(
            key=lambda child: child.catalog_product_count,
            reverse=True,
        )

    breadcrumbs = []
    if current_category:
        breadcrumbs = get_category_breadcrumbs(current_category)

    favorite_product_ids = []
    if request.user.is_authenticated:
        favorite_product_ids = list(Favorite.objects.filter(user=request.user).values_list('product_id', flat=True))

    comparison_product_ids = request.session.get('comparison', [])

    context = {
        'title': 'Каталог',
        'current_category': current_category,
        'current_category_children': current_category_children,
        'top_level_categories': top_level_categories,
        'products': products,
        'breadcrumbs': breadcrumbs,
        'favorite_product_ids': favorite_product_ids,
        'comparison_product_ids': comparison_product_ids,
        'brands_with_counts': brands_with_counts,
        'selected_brands': selected_brand_objects,
        'selected_brands_slugs': selected_brands_slugs,
        'price_range_min': price_range_min,
        'price_range_max': price_range_max,
    }
    return render(request, 'app/catalog.html', context)

def product_detail(request, product_id):
    # Create cache key for product detail view
    cache_key = f"product_detail_{product_id}"
    
    # Try to get data from cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return render(request, 'app/product_detail.html', cached_data)
    
    product = get_object_or_404(Product.objects.select_related('brand', 'category').prefetch_related('images', 'characteristics__characteristic', 'reviews'), id=product_id)

    recently_viewed = request.session.get('recently_viewed', [])
    if product_id in recently_viewed:
        recently_viewed.remove(product_id)
    recently_viewed.insert(0, product_id)
    request.session['recently_viewed'] = recently_viewed[:5]

    reviews = Review.objects.filter(product=product).order_by('-date')

    favorite_product_ids = []
    if request.user.is_authenticated:
        favorite_product_ids = list(Favorite.objects.filter(user=request.user).values_list('product_id', flat=True))

    review_stats = reviews.aggregate(
        average_rating=Avg('rating'),
        review_count=Sum(1)
    )

    if request.method == 'POST':
        if 'add_to_cart' in request.POST and request.user.is_authenticated:
            quantity = int(request.POST.get('quantity', 1))
            cart_order, _ = Order.objects.get_or_create(user=request.user, status='CART')
            cart_item, created = OrderItem.objects.get_or_create(
                order=cart_order,
                product=product,
                defaults={'quantity': 0}
            )
            
            new_quantity = cart_item.quantity + quantity
            if product.quantity > 0 and new_quantity > product.quantity:
                new_quantity = product.quantity
            
            if new_quantity > 0:
                cart_item.quantity = new_quantity
                cart_item.save()
            
            return redirect('cart')
        
        elif 'review_submit' in request.POST:
            form = ReviewForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.author = request.user
                review.product = product
                review.date = timezone.now()
                review.save()
                
                images = request.FILES.getlist('review_images')
                for image in images:
                    ReviewImage.objects.create(review=review, image=image)
                
                return redirect('product_detail', product_id=product.id)
    else:
        form = ReviewForm()

    similar_products = []
    if product.category:
        similar_products = Product.objects.filter(category=product.category).exclude(id=product_id).prefetch_related('images', 'reviews')[:10]

    breadcrumbs = []
    if product.category:
        breadcrumbs = get_category_breadcrumbs(product.category)

    discount_percentage = 0
    if product.old_price and product.price and product.old_price > product.price:
        discount_percentage = round(((product.old_price - product.price) / product.old_price) * 100)

    comparison_product_ids = request.session.get('comparison', [])
    
    # Голоса пользователя за отзывы
    user_review_votes = {}
    if request.user.is_authenticated:
        user_votes = ReviewVote.objects.filter(user=request.user, review__product=product)
        user_review_votes = {vote.review_id: vote.vote_type for vote in user_votes}

    # Рекомендации
    bought_together_products = get_bought_together_products(product, limit=4)

    context = {
        'title': product.title,
        'product': product,
        'reviews': reviews,
        'form': form,
        'breadcrumbs': breadcrumbs,
        'similar_products': similar_products,
        'average_rating': review_stats['average_rating'],
        'review_count': review_stats['review_count'] or 0,
        'favorite_product_ids': favorite_product_ids,
        'comparison_product_ids': comparison_product_ids,
        'discount_percentage': discount_percentage,
        'user_review_votes': user_review_votes,
        'bought_together': bought_together_products,
    }
    
    # Cache the data for 30 minutes (1800 seconds)
    # Убираем несериализуемые объекты из контекста для кэширования
    cacheable_context = {}
    for key, value in context.items():
        try:
            # Пытаемся сериализовать объект
            pickle.dumps(value)
            cacheable_context[key] = value
        except (TypeError, AttributeError):
            # Если не сериализуется, пропускаем
            continue
    
    cache.set(cache_key, cacheable_context, 1800)
    
    return render(request, 'app/product_detail.html', context)

from datetime import datetime, timedelta

@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).exclude(status='CART').prefetch_related('items__product__images').order_by('-created_at')
    
    cancellation_deadlines = {}
    for order in orders:
        # Разрешаем отмену в течение 1 часа, если статус "Оформлен" (CREATED)
        if order.status == 'CREATED':
            deadline = order.created_at + timedelta(hours=1)
            if timezone.now() < deadline:
                cancellation_deadlines[order.id] = deadline.isoformat()

    return render(request, 'app/my_orders.html', {
        'title': 'Мои заказы',
        'orders': orders,
        'cancellation_deadlines': cancellation_deadlines,
    })


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status == 'CREATED':
        if timezone.now() < order.created_at + timedelta(hours=1):
            order.status = 'CANCELLED'
            order.cancelled_by_user = True
            order.save()
            
            messages.success(request, f'Заказ №{order_id} успешно отменен.')
        else:
            messages.error(request, 'Время для отмены заказа (1 час) истекло.')
    else:
        messages.error(request, 'Этот заказ нельзя отменить.')

    return redirect('my_orders')

@user_passes_test(is_manager)
def manager_orders(request):
    STATUS_SEQUENCE = ['CREATED', 'ASSEMBLING', 'READY_FOR_PICKUP', 'COMPLETED']
    
    order_id = request.POST.get('order_id')
    new_status = request.POST.get('new_status')
    if order_id and new_status:
        try:
            order = Order.objects.get(id=order_id)
            current_status = order.status
            is_valid_transition = False
            
            if new_status == 'CANCELLED' and current_status not in ['COMPLETED', 'CANCELLED']:
                is_valid_transition = True
            elif current_status in STATUS_SEQUENCE and new_status in STATUS_SEQUENCE:
                if STATUS_SEQUENCE.index(new_status) > STATUS_SEQUENCE.index(current_status):
                    is_valid_transition = True
                    
            if is_valid_transition:
                # Если заказ выдан, фиксируем дату оплаты (так как оплата при получении)
                if new_status == 'COMPLETED' and order.paid_at is None:
                    order.paid_at = timezone.now()

                order.status = new_status
                order.save()
        except (Order.DoesNotExist, ValueError):
            pass

    query = request.GET.get('q', '')
    active_filter = request.GET.get('filter', 'all')
    
    orders_query = Order.objects.exclude(status='CART').select_related('user').prefetch_related('items__product').order_by('-created_at')
    
    if query:
        orders_query = orders_query.filter(
            Q(id__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query)
        )
    
    if active_filter != 'all':
        if active_filter == 'active':
            orders_query = orders_query.exclude(status__in=['COMPLETED', 'CANCELLED'])
        else:
            orders_query = orders_query.filter(status=active_filter)

    orders_with_transitions = []
    status_dict = dict(Order.STATUS_CHOICES)
    
    for order in orders_query:
        allowed_statuses = []
        current_status = order.status
        
        if current_status in STATUS_SEQUENCE:
            current_index = STATUS_SEQUENCE.index(current_status)
            for status in STATUS_SEQUENCE[current_index + 1:]:
                if status in status_dict:
                    allowed_statuses.append((status, status_dict[status]))
        
        if current_status not in ['COMPLETED', 'CANCELLED']:
            allowed_statuses.append(('CANCELLED', status_dict['CANCELLED']))
        
        orders_with_transitions.append({
            'order': order,
            'allowed_statuses': allowed_statuses
        })

    stats = {
        'total': orders_query.count(),
        'created': orders_query.filter(status='CREATED').count(),
        'assembling': orders_query.filter(status='ASSEMBLING').count(),
        'ready': orders_query.filter(status='READY_FOR_PICKUP').count(),
        'completed': orders_query.filter(status='COMPLETED').count(),
        'cancelled': orders_query.filter(status='CANCELLED').count(),
    }

    return render(request, 'app/manager_orders.html', {
        'title': 'Управление заказами',
        'orders_with_transitions': orders_with_transitions,
        'search_query': query or '',
        'DELIVERY_CHOICES': dict(Order.DELIVERY_CHOICES),
        'PAYMENT_CHOICES': dict(Order.PAYMENT_CHOICES),
        'all_statuses': Order.STATUS_CHOICES,
        'stats': stats,
        'active_filter': active_filter,
    })

@login_required
def order_complete(request):
    """
    Displays the order completion/thank you page.
    """
    context = {
        'title': 'Заказ оформлен',
    }
    
    return render(request, 'app/order_complete.html', context)



def home(request):
    """Renders the home page."""
    assert isinstance(request, HttpRequest)
    categories = Category.objects.filter(parent__isnull=True).prefetch_related('children').prefetch_related('product_set')[:6]
    popular_products = Product.objects.filter(category__isnull=False).select_related('brand', 'category').prefetch_related('images', 'reviews').order_by('-purchase_count', '-added_date')[:8]
    
    promotions = Promotion.objects.filter(is_active=True, show_on_home=True)[:2]
    
    # Определяем топ 3 товара по продажам для ХИТ
    top_products_ids = list(OrderItem.objects.filter(
        order__status__in=['AWAITING_PAYMENT', 'PAID', 'ASSEMBLING', 'SHIPPED', 'DELIVERING', 'AWAITING_PICKUP', 'ARRIVED', 'COMPLETED']
    ).values('product_id').annotate(
        total_sold=Sum('quantity')
    ).order_by('-total_sold')[:3].values_list('product_id', flat=True))
    
    for product in popular_products:
        product.is_hit = product.id in top_products_ids
    
    # Персональные рекомендации на основе истории просмотров
    recommended_products = get_personalized_recommendations(request, limit=8)
    
    for product in recommended_products:
        product.is_hit = product.id in top_products_ids
        
    # Слайды карусели
    from .models import HeroCarouselSlide
    hero_slides = HeroCarouselSlide.objects.filter(is_active=True).order_by('order', '-id')
    
    return render(
        request,
        'app/index.html',
        {
            'title':'Главная',
            'year':datetime.now().year,
            'home_categories': categories,
            'popular_products': popular_products,
            'promotions': promotions,
            'recommended_products': recommended_products,
            'hero_slides': hero_slides,
        }
    )

def contact(request):
    """Renders the contact page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/contact.html',
        {
            'title':'Контакты',
            'message':'Страница с нашими контактами.',
            'year':datetime.now().year,
        }
    )

def about(request):
    """Renders the about page."""
    assert isinstance(request, HttpRequest)
    return render(
        request,
        'app/about.html',
        {
            'title':'Добро пожаловать на страницу "О нас"!',
            'year':datetime.now().year,
        }
    )

def cyrillic_slugify(text):
    """
    Создает slug из текста с поддержкой кириллицы используя библиотеку transliterate
    """
    try:
        return transliterate_slugify(text)
    except Exception as e:
        print(f"Ошибка транслитерации: {e}")
        return slugify(text)

from .forms import BootstrapAuthenticationForm, ProductForm, ReviewForm, FeedbackForm, ProfileForm, ProductCharacteristicFormSet

@login_required
def add_product(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        formset = ProductCharacteristicFormSet(request.POST, instance=Product())
        if form.is_valid() and formset.is_valid():
            product = form.save(commit=False)
            product.author = request.user
            product.save()
            
            formset.instance = product
            formset.save()
            
            images = request.FILES.getlist('images')
            for image in images:
                ProductImage.objects.create(product=product, image=image)
            
            # Invalidate cache for this product and catalog
            invalidate_product_cache(product.id)
            invalidate_catalog_cache()
            
            return redirect('product_detail', product_id=product.id)
    else:
        form = ProductForm()
        formset = ProductCharacteristicFormSet(instance=Product())
    
    parent_categories = Category.objects.filter(parent__isnull=True).prefetch_related('children')

    return render(request, 'app/add_product.html', {
        'title': 'Добавление нового продукта',
        'form': form,
        'formset': formset,
        'parent_categories': parent_categories
    })
    
import re
from django.core.mail import send_mail
from django.conf import settings
import json
import random
import string
import threading

def _send_repair_emails(request_id):
    """Helper function to send repair emails in a background thread."""
    try:
        repair_request = RepairRequest.objects.get(id=request_id)
        
        # --- Send email to manager ---
        subject_manager = f"Новая заявка на ремонт #{repair_request.request_number}: {repair_request.tool_type}"
        message_manager = f"""
        Новая заявка на ремонт была получена:
        Номер заявки: {repair_request.request_number}
        Имя клиента: {repair_request.name}
        Телефон: {repair_request.phone}
        Email: {repair_request.email}
        Тип инструмента: {repair_request.tool_type}
        Описание поломки:
        {repair_request.description}
        """
        send_mail(
            subject_manager,
            message_manager,
            settings.DEFAULT_FROM_EMAIL,
            ['admin@mastertool.ru'],
            fail_silently=False,
        )

        # --- Send confirmation email to client ---
        subject_client = f"Ваша заявка №{repair_request.request_number} принята"
        message_client = f"""
        Здравствуйте, {repair_request.name}!

        Мы получили вашу заявку на ремонт инструмента: '{repair_request.tool_type}'.
        Номер вашей заявки: {repair_request.request_number}.

        Наш менеджер свяжется с вами по телефону {repair_request.phone} в течение 15 минут для подтверждения деталей.

        Спасибо, что выбрали наш сервисный центр!

        С уважением,
        Команда MasterTool
        """
        send_mail(
            subject_client,
            message_client,
            settings.DEFAULT_FROM_EMAIL,
            [repair_request.email],
            fail_silently=False,
        )
    except RepairRequest.DoesNotExist:
        # Log this error, the request ID was invalid
        print(f"Could not find RepairRequest with ID {request_id} to send emails.")
    except Exception as e:
        # Log this email sending error
        print(f"Error sending repair emails for request {request_id}: {e}")


def repair(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            phone = data.get('phone')
            email = data.get('email')
            tool_type = data.get('tool_type')
            description = data.get('description')

            if not all([name, phone, email, tool_type, description]):
                return JsonResponse({'status': 'error', 'message': 'Пожалуйста, заполните все поля.'}, status=400)

            # Валидация номера телефона
            if phone:
                cleaned_phone = re.sub(r'\D', '', str(phone))
                if len(cleaned_phone) != 11:
                    return JsonResponse({'status': 'error', 'message': 'Пожалуйста, введите корректный 11-значный номер телефона.'}, status=400)

            # Create the object without the number first to get an ID
            new_request = RepairRequest.objects.create(
                name=name,
                phone=phone,
                email=email,
                tool_type=tool_type,
                description=description
            )

            # Generate and save the user-facing request number
            date_str = timezone.now().strftime('%y%m%d')
            random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
            new_request.request_number = f"{date_str}-{random_part}{new_request.id}"
            new_request.save()

            # Start sending emails in a background thread
            email_thread = threading.Thread(target=_send_repair_emails, args=(new_request.id,))
            email_thread.start()

            return JsonResponse({'status': 'success', 'message': 'Ваша заявка успешно отправлена!'})

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Ошибка в формате запроса.'}, status=400)
        except Exception as e:
            # It's good practice to log the error `e` here
            return JsonResponse({'status': 'error', 'message': 'Произошла ошибка при сохранении заявки.'}, status=500)

    return render(request, 'app/repair.html', {
        'title': 'Ремонт и Сервисный центр',
    })

def videopost(request):
    return render(request, 'app/videopost.html',{'title':'Видео нашей работы'})

def news(request):
    all_promotions = Promotion.objects.filter(is_active=True).order_by('-created_at')
    all_news = News.objects.filter(is_published=True).order_by('-created_at')
    return render(request, 'app/news.html',
                  {
                  'title':'Новости и Акции',
                  'promotions': all_promotions,
                  'news_list': all_news,
                  }
                  )

def news_detail(request, slug):
    article = get_object_or_404(News, slug=slug, is_published=True)
    related_news = News.objects.filter(is_published=True).exclude(id=article.id).order_by('-created_at')[:3]
    return render(request, 'app/news_detail.html',
                  {
                  'title': article.title,
                  'article': article,
                  'related_news': related_news,
                  }
                  )

def useful_resources(request):
   
    resources = [
        {
            'title': 'Официальная документация Bosch',
            'url': 'https://www.bosch-pt.com/',
            'description': 'Сайт Bosch Professional с руководствами и инструкциями для электроинструментов.',
        },
        {
            'title': 'Makita Россия',
            'url': 'https://www.makita.ru/',
            'description': 'Официальный сайт Makita в России. Каталог инструментов и поддержка.',
        },
        {
            'title': 'Husqvarna - Официальный сайт',
            'url': 'https://www.husqvarna.com/',
            'description': 'Сайт Husqvarna с информацией о бензоинструментах и садовой технике.',
        },
        {
            'title': 'Каталог запчастей для инструментов',
            'url': 'https://www.220-volt.ru/',
            'description': 'Сайт с запчастями для электроинструментов и бензоинструментов.',
        },
        {
            'title': 'Советы по выбору инструментов',
            'url': 'https://vyboroved.ru/',
            'description': 'Ресурс с обзорами и рекомендациями по выбору инструментов.',
        },
        ]
    return render(request, 'app/useful_resources.html', {'resources': resources, 'title': 'Полезные ресурсы',})

def feedback(request):
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback_instance = form.save()

            # Формирование и отправка письма
            subject = f"Новый отзыв с сайта от {feedback_instance.name}"
            from_email = settings.DEFAULT_FROM_EMAIL
            to_email = ['admin@mastertool.ru']

            # HTML-содержимое письма
            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: sans-serif; }}
                    .container {{ padding: 20px; border: 1px solid #ddd; border-radius: 5px; max-width: 600px; }}
                    h2 {{ color: #333; }}
                    p {{ line-height: 1.6; }}
                    strong {{ color: #555; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>Новый отзыв с сайта MasterTool</h2>
                    <p><strong>Имя:</strong> {feedback_instance.name}</p>
                    <p><strong>Email:</strong> {feedback_instance.email}</p>
                    <hr>
                    <p><strong>Общая оценка:</strong> {'&#9733;' * feedback_instance.overall_rating}{'&#9734;' * (5 - feedback_instance.overall_rating)} ({feedback_instance.overall_rating}/5)</p>
                    <p><strong>Оценка удобства:</strong> {feedback_instance.get_usability_rating_display()}</p>
                    <p><strong>Частота посещений:</strong> {feedback_instance.get_visit_frequency_display()}</p>
                    <hr>
                    <p><strong>Комментарий:</strong></p>
                    <p>{feedback_instance.comments or 'Не оставлен'}</p>
                </div>
            </body>
            </html>
            """
            
            send_mail(subject, '', from_email, to_email, fail_silently=False, html_message=html_content)

            return render(request, 'app/feedback_thanks.html', {
                'title': 'Спасибо за отзыв',
            })
    else:
        form = FeedbackForm()

    return render(request, 'app/feedback.html', {
        'form': form,
        'title': 'Обратная связь',
    })

def registration(request):
    if request.method == "POST":
        form = ExtendedRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = ExtendedRegistrationForm()
    
    return render(
        request,
        'app/registration.html',
        {
            'title': 'Регистрация',
            'form': form,
            'year': datetime.now().year,
        }
    )

@login_required
def profile_edit_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    context = {
        'title': 'Редактировать профиль',
        'form': form
    }
    return render(request, 'app/profile_edit.html', context)


def login_view(request):
    if request.method == "POST":
        form = BootstrapAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
    else:
        form = BootstrapAuthenticationForm()
    return render(request, 'app/login.html', {'form': form})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related('items__product__images'), id=order_id)
    if not is_manager(request.user) and order.user != request.user:
        return HttpResponseForbidden("У вас нет прав для просмотра этого заказа.")

    order_items = order.items.all()

    context = {
        'title': f'Детали заказа #{order.id}',
        'order': order,
        'order_items': order_items,
    }
    return render(request, 'app/order_detail.html', context)


@login_required
def pay_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Only allow paying AWAITING_PAYMENT orders
    if order.status != 'AWAITING_PAYMENT':
        messages.error(request, 'Невозможно оплатить этот заказ.')
        return redirect('order_detail', order_id=order_id)
    
    order.status = 'PAID'
    order.paid_at = timezone.now()
    order.save()
    
    messages.success(request, 'Заказ успешно оплачен!')
    return redirect('order_detail', order_id=order_id)


@require_POST
@user_passes_test(is_manager)
def update_stock(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        new_quantity = int(data.get('quantity'))

        if product_id is None or new_quantity < 0:
            return JsonResponse({'status': 'error', 'message': 'Неверные данные.'}, status=400)

        product = get_object_or_404(Product, id=product_id)
        product.quantity = new_quantity
        product.save()
        
        return JsonResponse({'status': 'success', 'product_id': product.id, 'new_quantity': product.quantity})
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Неверный формат запроса.'}, status=400)
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Товар не найден.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@user_passes_test(is_manager)
def bulk_update_stock(request):
    try:
        data = json.loads(request.body)
        action = data.get('action')
        product_ids = data.get('product_ids')

        if not all([action, product_ids]):
            return JsonResponse({'status': 'error', 'message': 'Отсутствуют необходимые данные.'}, status=400)
            
        products = Product.objects.filter(id__in=product_ids)
        
        if action == 'set_quantity':
            quantity = int(data.get('quantity', 0))
            if quantity < 0:
                return JsonResponse({'status': 'error', 'message': 'Количество не может быть отрицательным.'}, status=400)
            updated_count = products.update(quantity=quantity)
            return JsonResponse({'status': 'success', 'message': f'{updated_count} товаров обновлено.', 'action': action, 'new_quantity': quantity})

        elif action == 'remove_from_sale':
            updated_count = products.update(quantity=0)
            return JsonResponse({'status': 'success', 'message': f'{updated_count} товаров снято с продажи.', 'action': action})

        elif action == 'delete':
            deleted_count, _ = products.delete()
            return JsonResponse({'status': 'success', 'message': f'{deleted_count} товаров удалено.', 'action': action})

        else:
            return JsonResponse({'status': 'error', 'message': 'Неизвестное действие.'}, status=400)

    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Неверный формат запроса.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@user_passes_test(is_manager)
def manager_stock(request):
    products = Product.objects.all().order_by('title')
    
    if request.method == 'POST' and not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        for product in products:
            quantity_to_add = request.POST.get(f'quantity_{product.id}')
            if quantity_to_add:
                try:
                    quantity_to_add = int(quantity_to_add)
                    if quantity_to_add > 0:
                        product.quantity += quantity_to_add
                        product.save()
                except ValueError:
                    pass
        return redirect('manager_stock')

    return render(request, 'app/manager_stock.html', {
        'title': 'Управление складом',
        'products': products,
    })

@login_required
def reorder(request, order_id):
    original_order = get_object_or_404(Order, id=order_id, user=request.user)
    cart_order, created = Order.objects.get_or_create(user=request.user, status='CART')
    
    for item_to_reorder in original_order.items.all():
        product = item_to_reorder.product
        
        if product.quantity > 0:
            cart_item, created = OrderItem.objects.get_or_create(
                order=cart_order,
                product=product,
                defaults={'quantity': 0}
            )
            
            desired_quantity = cart_item.quantity + item_to_reorder.quantity
            
            if desired_quantity > product.quantity:
                new_quantity = product.quantity
            else:
                new_quantity = desired_quantity
            
            cart_item.quantity = new_quantity
            cart_item.save()
            
    return redirect('cart')

@user_passes_test(is_manager)
def manager_repairs_dashboard(request):
    if request.method == 'POST':
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')

        if action == 'delete':
            try:
                repair_request = RepairRequest.objects.get(id=request_id)
                repair_request.delete()
                # Optionally, add a success message to Django's messages framework
            except RepairRequest.DoesNotExist:
                # Optionally, handle the error
                pass
        else: # Default action is to update status
            new_status = request.POST.get('status')
            if request_id and new_status:
                try:
                    repair_request = RepairRequest.objects.get(id=request_id)
                    repair_request.status = new_status
                    repair_request.save()
                except RepairRequest.DoesNotExist:
                    pass
        return redirect('manager_repairs')

    # GET request handling
    all_requests = RepairRequest.objects.all()

    # Calculate stats
    stats = {
        'total': all_requests.count(),
        'new': all_requests.filter(status='NEW').count(),
        'in_progress': all_requests.filter(status__in=['DIAGNOSING', 'IN_PROGRESS']).count(),
        'ready': all_requests.filter(status='READY').count(),
    }

    context = {
        'title': 'Управление заявками на ремонт',
        'requests': all_requests,
        'stats': stats,
        'status_choices': RepairRequest.STATUS_CHOICES,
    }
    return render(request, 'app/manager_repairs.html', context)


def custom_404_view(request, exception):
    return render(request, 'app/errors/404_custom.html', {}, status=404)

def custom_500_view(request):
    return render(request, 'app/errors/500_custom.html', {}, status=500)

def brand_detail(request, slug):
    brand = get_object_or_404(Brand, slug=slug)
    products = Product.objects.filter(brand=brand).prefetch_related('images', 'reviews')
    
    context = {
        'title': f'Товары бренда {brand.name}',
        'brand': brand,
        'products': products,
    }
    return render(request, 'app/brand_detail.html', context)

def get_product_details_json(request, product_id):
    """
    API endpoint to get product details for the Quick View modal.
    """
    try:
        product = get_object_or_404(
            Product.objects.prefetch_related('images', 'characteristics__characteristic'), 
            id=product_id
        )

        first_image = product.images.first()
        image_url = first_image.image.url if first_image else ''

        # Get a few characteristics
        characteristics = list(product.characteristics.all().values_list(
            'characteristic__name', 'value'
        )[:3]) # Limit to 3 for a "quick" view

        data = {
            'id': product.id,
            'name': product.title,
            'price': f'{product.price:g}', # Use 'g' to remove trailing zeros
            'old_price': f'{product.old_price:g}' if product.old_price and product.old_price > product.price else None,
            'image_url': image_url,
            'product_url': product.get_absolute_url(),
            'in_stock': product.quantity > 0,
            'characteristics': [f"{name}: {value}" for name, value in characteristics],
        }
        return JsonResponse(data)

    except Product.DoesNotExist:
        return JsonResponse({'error': 'Товар не найден'}, status=404)
    except Exception as e:
        # Log the error e
        return JsonResponse({'error': 'Произошла ошибка'}, status=500)

from django.views.decorators.http import require_GET

@require_GET
def product_quick_view(request, product_id):
    """
    Returns a JSON response with detailed product information for the quick view modal.
    """
    # Create cache key based on product ID
    cache_key = f'product_quick_view_{product_id}'
    
    # Try to get data from cache first
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse(cached_data)
    
    product = get_object_or_404(
        Product.objects.select_related('brand').prefetch_related(
            'images', 'characteristics__characteristic', 'reviews'
        ),
        id=product_id
    )

    images_data = [
        {'url': img.image.url} for img in product.images.all()
    ]
    if not images_data:
        images_data.append({'url': static('app/content/no_image.png')})

    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = Favorite.objects.filter(user=request.user, product=product).exists()
    
    # Using Decimal is better for price formatting in templates, but for JSON, float is fine.
    # Format with thousands separators (spaces)
    price_str = f'{product.price:,.0f}'.replace(",", " ")
    old_price_str = f'{product.old_price:,.0f}'.replace(",", " ") if product.old_price and product.old_price > product.price else None

    features = [{
        'name': pc.characteristic.name,
        'value': pc.value
    } for pc in product.characteristics.all()[:4]]

    data = {
        'id': product.id,
        'title': product.title,
        'brand': product.brand.name.upper() if product.brand else '',
        'brand_url': reverse('catalog') + f"?brand={product.brand.slug}" if product.brand else "#",
        'specs_line': product.get_specs_line,
        'price': price_str,
        'old_price': old_price_str,
        'images': images_data,
        'image_url': images_data[0]['url'] if images_data else '',
        'is_favorited': is_favorited,
        'features': features,
        'detail_url': product.get_absolute_url(),
        'add_to_cart_url': reverse('add_to_cart_ajax'),
        'in_stock': product.quantity > 0,
        'average_rating': float(product.average_rating) if product.average_rating is not None else 0.0, # Pass average rating
        'review_count': product.reviews.count() # Pass review count
    }
    
    # Cache the data for 30 minutes (1800 seconds)
    cache.set(cache_key, data, 1800)
    
    return JsonResponse(data)


@require_POST
@login_required
def add_to_cart_ajax(request):
    """
    Handles adding a product to the cart via an AJAX request.
    """
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))

        product = get_object_or_404(Product, id=product_id)
        cart_order, _ = Order.objects.get_or_create(user=request.user, status='CART')
        
        cart_item, created = OrderItem.objects.get_or_create(
            order=cart_order,
            product=product,
            defaults={'quantity': 0}
        )

        new_quantity = cart_item.quantity + quantity
        # Allow pre-orders if quantity is 0
        if product.quantity > 0 and new_quantity > product.quantity:
            return JsonResponse({
                'status': 'error',
                'message': f'Только {product.quantity} шт. в наличии'
            }, status=400)
        
        cart_item.quantity = new_quantity
        cart_item.save()

        # Get total number of items in cart
        total_items = OrderItem.objects.filter(order=cart_order).aggregate(Sum('quantity'))['quantity__sum']

        return JsonResponse({
            'status': 'success',
            'message': 'Товар добавлен в корзину',
            'total_items': total_items if total_items is not None else 0,
            'product_title': product.title # Added product title
        })

    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Товар не найден'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def privacy_policy(request):
    """Страница политики конфиденциальности"""
    return render(request, 'app/privacy_policy.html', {'title': 'Политика конфиденциальности'})


def terms_of_use(request):
    """Страница условий использования"""
    return render(request, 'app/terms_of_use.html', {'title': 'Условия использования'})


def delivery(request):
    """Страница доставки"""
    return render(request, 'app/delivery.html', {'title': 'Доставка'})


def payment(request):
    """Страница оплаты"""
    return render(request, 'app/payment.html', {'title': 'Оплата'})


def warranty(request):
    """Страница гарантии"""
    return render(request, 'app/warranty.html', {'title': 'Гарантия'})


@login_required
@require_POST
def review_helpful_vote(request):
    """
    Обработка голосования за полезность отзыва (helpful/not helpful).
    """
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Авторизуйтесь для голосования'}, status=401)
    
    try:
        data = json.loads(request.body)
        review_id = data.get('review_id')
        action = data.get('action')

        if not review_id or action not in ['helpful', 'not_helpful']:
            return JsonResponse({'status': 'error', 'message': 'Неверные данные'}, status=400)

        review = get_object_or_404(Review, id=review_id)

        # Проверяем, не голосовал ли уже пользователь
        existing_vote = ReviewVote.objects.filter(user=request.user, review=review).first()
        
        if existing_vote:
            if existing_vote.vote_type == action:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Вы уже голосовали так'
                }, status=400)
            
            # Меняем голос
            if action == 'helpful':
                review.helpful_count += 1
                review.not_helpful_count -= 1
            else:
                review.not_helpful_count += 1
                review.helpful_count -= 1
            
            existing_vote.vote_type = action
            existing_vote.save()
        else:
            # Новый голос
            ReviewVote.objects.create(user=request.user, review=review, vote_type=action)
            
            if action == 'helpful':
                review.helpful_count += 1
            else:
                review.not_helpful_count += 1

        review.save()

        return JsonResponse({
            'status': 'success',
            'helpful_count': review.helpful_count,
            'not_helpful_count': review.not_helpful_count,
            'has_voted': True
        })

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Неверный формат данных'}, status=400)
    except Review.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Отзыв не найден'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ==================== PRODUCT COMPARISON ====================

def get_comparison_products(request):
    """Получение списка товаров для сравнения из сессии."""
    comparison_ids = request.session.get('comparison', [])
    products = []
    if comparison_ids:
        products = list(Product.objects.filter(id__in=comparison_ids).prefetch_related('images', 'characteristics', 'brand', 'reviews'))
    return products


@require_POST
def toggle_compare(request):
    """
    Добавление/удаление товара из списка сравнения.
    """
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        check_only = data.get('check_only', False)
        
        comparison = request.session.get('comparison', [])
        
        # Если check_only или product_id == 0, просто возвращаем текущее состояние
        if check_only or product_id == 0 or product_id == "0":
            return JsonResponse({
                'status': 'success',
                'comparison_count': len(comparison),
                'comparison_ids': comparison
            })
        
        if not product_id:
            return JsonResponse({'status': 'error', 'message': 'Не указан товар'}, status=400)
        
        # Convert to int for database query
        try:
            product_id_int = int(product_id)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Неверный ID товара'}, status=400)
        
        product = get_object_or_404(Product, id=product_id_int)
        
        # Check if product is in comparison (compare as strings for consistency)
        product_id_str = str(product_id_int)
        is_in_comparison = product_id_str in comparison or product_id_int in comparison
        
        if is_in_comparison:
            # Remove from comparison
            if product_id_str in comparison:
                comparison.remove(product_id_str)
            if product_id_int in comparison:
                comparison.remove(product_id_int)
            message = 'Товар удален из сравнения'
        else:
            if len(comparison) >= 4:
                return JsonResponse({
                    'status': 'error', 
                    'message': 'Максимум 4 товара для сравнения'
                }, status=400)
            comparison.append(product_id_int)
            message = 'Товар добавлен в сравнение'
        
        request.session['comparison'] = comparison
        request.session.modified = True
        
        return JsonResponse({
            'status': 'success',
            'message': message,
            'is_in_comparison': not is_in_comparison,
            'comparison_count': len(comparison),
            'product_id': product_id_int
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Неверный формат данных'}, status=400)
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Товар не найден'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@require_POST
def clear_comparison(request):
    """Очистка списка сравнения."""
    request.session['comparison'] = []
    request.session.modified = True
    return JsonResponse({'status': 'success', 'message': 'Список сравнения очищен'})


def comparison_view(request):
    """
    Страница сравнения товаров.
    """
    products = get_comparison_products(request)
    
    if not products:
        return render(request, 'app/comparison.html', {
            'title': 'Сравнение товаров',
            'products': [],
            'comparison_categories': [],
            'all_characteristics': [],
            'is_empty': True,
        })
    
    comparison_categories = []
    all_characteristics = set()
    product_characteristics = {}
    
    for product in products:
        chars = {}
        for char in product.characteristics.all():
            chars[char.characteristic.name] = char.value
            all_characteristics.add(char.characteristic.name)
        product_characteristics[product.id] = chars
    
    all_characteristics = sorted(all_characteristics)
    
    # Characteristics where HIGHER is better
    higher_is_better = ['мощность', 'емкость', 'объем', 'мощность двигателя', 'ток', 'напряжение', 'скорость', 'производительность', 'ресурс', 'длина', 'ширина', 'высота', 'вес', 'диаметр', 'частота']
    
    # Characteristics where LOWER is better
    lower_is_better = ['цена', 'расход', 'потребление', 'уровень шума', 'время', 'зарядка', 'заряд']
    
    for char_name in all_characteristics:
        category_chars = []
        numeric_values = []
        
        for product in products:
            raw_value = product_characteristics.get(product.id, {}).get(char_name, '—')
            numeric_value = None
            
            # Try to extract numeric value
            if raw_value != '—':
                import re
                numbers = re.findall(r'[\d.]+', str(raw_value))
                if numbers:
                    try:
                        numeric_value = float(numbers[0].replace(',', '.'))
                    except:
                        pass
            
            category_chars.append({
                'product_id': product.id,
                'value': raw_value,
                'numeric_value': numeric_value
            })
            if numeric_value is not None:
                numeric_values.append(numeric_value)
        
        # Determine best value
        is_numeric = len(numeric_values) == len(products) and len(numeric_values) > 0
        
        if is_numeric:
            char_lower = char_name.lower()
            if any(term in char_lower for term in lower_is_better):
                best_value = min(numeric_values)
                best_type = 'lower'
            else:
                best_value = max(numeric_values)
                best_type = 'higher'
        else:
            best_value = None
            best_type = None
        
        # Mark best values
        for char in category_chars:
            if best_value is not None and char['numeric_value'] == best_value:
                char['is_best'] = True
            else:
                char['is_best'] = False
        
        comparison_categories.append({
            'name': char_name,
            'values': category_chars,
            'is_comparable': is_numeric
        })
    
    min_product_price = min(p.price for p in products) if products else None
    max_quantity = max(p.quantity for p in products) if products else 0

    return render(request, 'app/comparison.html', {
        'title': 'Сравнение товаров',
        'products': products,
        'product_characteristics': product_characteristics,
        'comparison_categories': comparison_categories,
        'all_characteristics': all_characteristics,
        'is_empty': False,
        'min_product_price': min_product_price,
        'max_quantity': max_quantity,
    })


# ==================== ANALYTICS DASHBOARD ====================

@user_passes_test(is_manager)
def analytics_dashboard(request):
    """Панель аналитики для администратора"""
    from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
    from django.utils import timezone
    
    now = timezone.localtime(timezone.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    
    # Получаем все заказы (кроме корзин)
    all_orders = Order.objects.exclude(status='CART').exclude(status__isnull=True)
    paid_orders = all_orders.filter(status='PAID')
    completed_orders = all_orders.filter(status='COMPLETED')
    
    # ============ ОСНОВНЫЕ МЕТРИКИ ============
    # За последние 30 дней (используем order_date для продаж)
    orders_last_30_days = all_orders.filter(order_date__gte=thirty_days_ago)
    revenue_last_30_days = orders_last_30_days.exclude(status__in=['CANCELLED']).aggregate(
        total=Sum('total_price')
    )['total'] or 0
    
    # За последние 7 дней
    orders_last_7_days = all_orders.filter(order_date__gte=seven_days_ago)
    revenue_last_7_days = orders_last_7_days.exclude(status__in=['CANCELLED']).aggregate(
        total=Sum('total_price')
    )['total'] or 0
    
    # Прошлый период (30 дней перед текущими 30 днями)
    sixty_days_ago = now - timedelta(days=60)
    orders_previous_period = all_orders.filter(order_date__gte=sixty_days_ago, order_date__lt=thirty_days_ago)
    revenue_previous_period = orders_previous_period.exclude(status__in=['CANCELLED']).aggregate(
        total=Sum('total_price')
    )['total'] or 0
    
    # Расчет изменений
    revenue_change = 0
    if revenue_previous_period > 0:
        revenue_change = ((revenue_last_30_days - revenue_previous_period) / revenue_previous_period) * 100
    
    order_count_change = 0
    previous_count = orders_previous_period.count()
    current_count = orders_last_30_days.count()
    if previous_count > 0:
        order_count_change = ((current_count - previous_count) / previous_count) * 100
    
    # Средний чек
    avg_order_value = 0
    if completed_orders.exists():
        avg_order_value = completed_orders.aggregate(avg=Avg('total_price'))['avg'] or 0
    
    # Конверсия (завершенные / оплаченные)
    conversion_rate = 0
    if paid_orders.exists():
        conversion_rate = (completed_orders.count() / paid_orders.count()) * 100
    
    # ============ ГРАФИК ПРОДАЖ ПО ДНЯМ (30 дней) ============
    daily_sales = all_orders.filter(
        order_date__gte=thirty_days_ago
    ).exclude(status__in=['CANCELLED']).annotate(
        day=TruncDay('order_date')
    ).values('day').annotate(
        revenue=Sum('total_price'),
        count=Count('id')
    ).order_by('day')
    
    daily_labels = []
    daily_revenue = []
    daily_count = []
    
    # Создаем словарь для быстрого поиска (используем.date() для консистентности)
    sales_dict = {}
    for item in daily_sales:
        if item['day']:
            day_date = item['day'].date()
            sales_dict[day_date] = {'revenue': float(item['revenue']), 'count': item['count']}
    
    # Генерируем даты от (сегодня - 29 дней) до сегодня
    today = now.date()
    for i in range(30):
        day = today - timedelta(days=29-i)
        daily_labels.append(day.strftime('%d.%m'))
        if day in sales_dict:
            daily_revenue.append(sales_dict[day]['revenue'])
            daily_count.append(sales_dict[day]['count'])
        else:
            daily_revenue.append(0)
            daily_count.append(0)
    
    # ============ ГРАФИК ПРОДАЖ ПО МЕСЯЦАМ (12 месяцев) ============
    twelve_months_ago = now - timedelta(days=365)
    monthly_sales = all_orders.filter(
        order_date__gte=twelve_months_ago
    ).exclude(status__in=['CANCELLED']).annotate(
        month=TruncMonth('order_date')
    ).values('month').annotate(
        revenue=Sum('total_price')
    ).order_by('month')
    
    monthly_labels = []
    monthly_revenue = []
    
    for item in monthly_sales:
        monthly_labels.append(item['month'].strftime('%b %Y'))
        monthly_revenue.append(float(item['revenue']))
    
    # ============ ТОП ТОВАРОВ ============
    top_products = OrderItem.objects.filter(
        order__in=all_orders.exclude(status__in=['CANCELLED', 'CART'])
    ).values(
        'product__title', 'product__id'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('product__price')
    ).order_by('-total_sold')[:10]
    
    # Создаем список словарей для шаблона
    top_products_list = []
    for item in top_products:
        title = item['product__title']
        if len(title) > 25:
            title = title[:25] + '...'
        top_products_list.append({
            'title': title,
            'total_sold': item['total_sold'],
            'total_revenue': float(item['total_revenue'])
        })
    
    top_product_labels = [item['product__title'][:25] + '...' if len(item['product__title']) > 25 else item['product__title'] for item in top_products]
    top_product_sold = [item['total_sold'] for item in top_products]
    top_product_revenue = [float(item['total_revenue']) for item in top_products]
    
    # ============ ТОП КАТЕГОРИЙ ============
    top_categories = OrderItem.objects.filter(
        order__in=all_orders.exclude(status__in=['CANCELLED', 'CART'])
    ).values(
        'product__category__name'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('product__price')
    ).order_by('-total_sold')[:8]
    
    category_labels = [item['product__category__name'] or 'Без категории' for item in top_categories]
    category_sold = [item['total_sold'] for item in top_categories]
    
    # ============ ТОП БРЕНДОВ ============
    top_brands = OrderItem.objects.filter(
        order__in=all_orders.exclude(status__in=['CANCELLED', 'CART'])
    ).values(
        'product__brand__name'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('product__price')
    ).order_by('-total_sold')[:8]
    
    brand_labels = [item['product__brand__name'] or 'Без бренда' for item in top_brands]
    brand_sold = [item['total_sold'] for item in top_brands]
    
    # ============ СТАТУСЫ ЗАКАЗОВ ============
    status_distribution = all_orders.values('status').annotate(count=Count('id'))
    status_labels = []
    status_counts = []
    status_colors = []
    
    status_colors_map = {
        'AWAITING_PAYMENT': '#F59E0B',
        'PAID': '#3B82F6',
        'ASSEMBLING': '#8B5CF6',
        'SHIPPED': '#6366F1',
        'DELIVERING': '#EC4899',
        'AWAITING_PICKUP': '#14B8A6',
        'ARRIVED': '#10B981',
        'COMPLETED': '#22C55E',
        'CANCELLED': '#EF4444',
        'DEFECT_RETURN': '#DC2626',
    }
    
    status_names_map = dict(Order.STATUS_CHOICES)
    
    for item in status_distribution:
        status_labels.append(status_names_map.get(item['status'], item['status']))
        status_counts.append(item['count'])
        status_colors.append(status_colors_map.get(item['status'], '#6B7280'))
    
    # ============ СПОСОБЫ ОПЛАТЫ ============
    payment_methods = all_orders.exclude(payment_method__isnull=True).values('payment_method').annotate(count=Count('id'))
    payment_labels = []
    payment_counts = []
    
    payment_names_map = dict(Order.PAYMENT_CHOICES)
    
    for item in payment_methods:
        payment_labels.append(payment_names_map.get(item['payment_method'], item['payment_method']))
        payment_counts.append(item['count'])
    
    # ============ СПОСОБЫ ДОСТАВКИ ============
    delivery_methods = all_orders.exclude(delivery_method__isnull=True).values('delivery_method').annotate(count=Count('id'))
    delivery_labels = []
    delivery_counts = []
    
    delivery_names_map = dict(Order.DELIVERY_CHOICES)
    
    for item in delivery_methods:
        delivery_labels.append(delivery_names_map.get(item['delivery_method'], item['delivery_method']))
        delivery_counts.append(item['count'])
    
    # ============ НОВЫЕ ПОЛЬЗОВАТЕЛИ ============
    from django.contrib.auth.models import User
    users_last_30_days = User.objects.filter(date_joined__gte=thirty_days_ago).count()
    users_last_7_days = User.objects.filter(date_joined__gte=seven_days_ago).count()
    total_users = User.objects.count()
    
    context = {
        'title': 'Аналитика',
        # Основные метрики
        'revenue_last_30_days': revenue_last_30_days,
        'revenue_last_7_days': revenue_last_7_days,
        'revenue_change': round(revenue_change, 1),
        'order_count_last_30': current_count,
        'order_count_change': round(order_count_change, 1),
        'avg_order_value': avg_order_value,
        'conversion_rate': round(conversion_rate, 1),
        'total_users': total_users,
        'new_users_30_days': users_last_30_days,
        'new_users_7_days': users_last_7_days,
        
        # Графики
        'daily_labels': daily_labels,
        'daily_revenue': daily_revenue,
        'daily_count': daily_count,
        
        'monthly_labels': monthly_labels,
        'monthly_revenue': monthly_revenue,
        
        'top_product_labels': top_product_labels,
        'top_product_sold': top_product_sold,
        'top_product_revenue': top_product_revenue,
        'top_products_list': top_products_list,
        
        'category_labels': category_labels,
        'category_sold': category_sold,
        
        'brand_labels': brand_labels,
        'brand_sold': brand_sold,
        
        'status_labels': status_labels,
        'status_counts': status_counts,
        'status_colors': status_colors,
        
        'payment_labels': payment_labels,
        'payment_counts': payment_counts,
        
        'delivery_labels': delivery_labels,
        'delivery_counts': delivery_counts,
    }
    
    return render(request, 'app/analytics.html', context)


# ==================== AI RECOMMENDATIONS ====================

def get_bought_together_products(product, limit=4):
    """
    Получает товары, которые чаще всего покупают вместе с данным товаром.
    """
    from django.db.models import Count
    
    # Находим заказы, содержащие этот товар
    orders_with_product = OrderItem.objects.filter(
        product=product,
        order__status__in=['PAID', 'ASSEMBLING', 'SHIPPED', 'DELIVERING', 'AWAITING_PICKUP', 'ARRIVED', 'COMPLETED']
    ).values_list('order_id', flat=True)
    
    if not orders_with_product:
        return []
    
    # Находим другие товары в этих заказах (кроме текущего)
    related_items = OrderItem.objects.filter(
        order_id__in=orders_with_product,
    ).exclude(product=product).values('product_id').annotate(
        purchase_count=Count('id')
    ).order_by('-purchase_count')[:limit]
    
    product_ids = [item['product_id'] for item in related_items]
    
    if not product_ids:
        return []
    
    products = Product.objects.filter(
        id__in=product_ids,
        quantity__gt=0
    ).prefetch_related('images', 'reviews')
    
    # Сохраняем порядок по популярности
    product_order = {pid: idx for idx, pid in enumerate(product_ids)}
    products = sorted(products, key=lambda p: product_order.get(p.id, 999))
    
    return products


def get_similar_products(product, limit=6):
    """
    Получает похожие товары из той же категории.
    """
    if not product.category:
        return Product.objects.filter(
            quantity__gt=0
        ).select_related('brand', 'category').prefetch_related('images', 'reviews').order_by('-purchase_count', '-added_date')[:limit]
    
    products = Product.objects.filter(
        category=product.category,
        quantity__gt=0
    ).exclude(id=product.id).select_related('brand', 'category').prefetch_related('images', 'reviews')
    
    # Добавляем сортировку по бренду, если есть
    if product.brand:
        products = sorted(products, key=lambda p: (p.brand_id != product.brand_id, -p.purchase_count))
    else:
        products = list(products.order_by('-purchase_count', '-added_date'))
    
    return products[:limit]


def get_personalized_recommendations(request, limit=8):
    """
    Персональные рекомендации на основе истории просмотров.
    """
    viewed_products = request.session.get('recently_viewed', [])
    
    if not viewed_products:
        return Product.objects.filter(
            quantity__gt=0
        ).select_related('brand', 'category').prefetch_related('images', 'reviews').order_by('-purchase_count', '-added_date')[:limit]
    
    # На основе последних просмотров находим похожие товары
    last_viewed_id = viewed_products[0] if viewed_products else None
    
    if last_viewed_id:
        try:
            last_product = Product.objects.get(id=last_viewed_id)
            # Получаем товары из той же категории
            similar = Product.objects.filter(
                category=last_product.category,
                quantity__gt=0
            ).exclude(id__in=viewed_products).select_related('brand', 'category').prefetch_related('images', 'reviews')[:limit]
            
            if similar:
                return similar
        except Product.DoesNotExist:
            pass
    
    # Fallback: популярные товары
    return Product.objects.filter(
        quantity__gt=0
    ).prefetch_related('images', 'reviews').order_by('-purchase_count', '-added_date')[:limit]


@login_required
@user_passes_test(is_manager)
def edit_product(request, product_id):
    """
    Редактирование продукта
    """
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        formset = ProductCharacteristicFormSet(request.POST, instance=product)
        
        if form.is_valid() and formset.is_valid():
            # Сохраняем продукт
            product = form.save(commit=False)
            product.save()
            
            # Сохраняем характеристики
            formset.instance = product
            formset.save()
            
            # Сохраняем изображения
            images = request.FILES.getlist('images')
            for image in images:
                ProductImage.objects.create(product=product, image=image)
            
            # Invalidate cache for this product and catalog
            invalidate_product_cache(product.id)
            invalidate_catalog_cache()
            
            return redirect('product_detail', product_id=product.id)
    else:
        form = ProductForm(instance=product)
        formset = ProductCharacteristicFormSet(instance=product)
    
    parent_categories = Category.objects.filter(parent__isnull=True).prefetch_related('children')
    
    return render(request, 'app/edit_product.html', {
        'title': 'Редактирование продукта',
        'form': form,
        'formset': formset,
        'parent_categories': parent_categories,
        'product': product
    })


@login_required
@user_passes_test(is_manager)
def delete_product(request, product_id):
    """
    Удаление продукта
    """
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == "POST":
        # Удаляем продукт
        product.delete()
        
        # Invalidate cache for catalog (since a product was removed)
        invalidate_catalog_cache()
        
        messages.success(request, 'Продукт успешно удален.')
        return redirect('catalog')
    
    return render(request, 'app/delete_product.html', {
        'title': 'Удаление продукта',
        'product': product
    })

