from .models import Category, Order, OrderItem
from django.db.models import Sum

def categories_processor(request):
    top_level_categories = Category.objects.filter(parent__isnull=True).prefetch_related('children').prefetch_related('product_set')
    return {
        'all_categories_for_menu': top_level_categories,
    }

def cart_item_count(request):
    if request.user.is_authenticated:
        try:
            cart_order = Order.objects.get(user=request.user, status='CART')
            total_quantity = OrderItem.objects.filter(order=cart_order).aggregate(Sum('quantity'))['quantity__sum']
            return {'cart_item_count': total_quantity if total_quantity is not None else 0}
        except Order.DoesNotExist:
            return {'cart_item_count': 0}
    return {'cart_item_count': 0}
