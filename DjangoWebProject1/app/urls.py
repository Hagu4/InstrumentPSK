from datetime import datetime
from django.urls import path
from app.views import catalog, product_detail, cart, my_orders, manager_orders
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from app import forms, views
from app.password_reset import SafePasswordResetForm

urlpatterns = [
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('live-search/', views.live_search, name='live_search'),
    path('api/product/<int:product_id>/', views.get_product_details_json, name='get_product_details_json'),
    path('api/product/<int:product_id>/quick-view/', views.product_quick_view, name='product_quick_view'),
    path('catalog/', catalog, name='catalog'),
    path('catalog/category/<slug:category_slug>/', views.catalog, name='catalog_category'),
    path('brand/<slug:slug>/', views.brand_detail, name='brand_detail'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('product/<int:product_id>/toggle_favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('cart/', cart, name='cart'),
    path('cart/apply-promo/', views.apply_promo_code, name='apply_promo_code'),
    path('cart/remove-promo/', views.remove_promo_code, name='remove_promo_code'),
    path('my-orders/', my_orders, name='my_orders'),
    path('my-orders/cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('manager-orders/', manager_orders, name='manager_orders'),
    # path('manager/repairs/', views.manager_repairs_dashboard, name='manager_repairs'),
    path('manager-stock/', views.manager_stock, name='manager_stock'),
    path('manager-analytics/', views.analytics_dashboard, name='manager_analytics'),
    path('ajax/add-to-cart/', views.add_to_cart_ajax, name='add_to_cart_ajax'),
    path('ajax/update-stock/', views.update_stock, name='ajax_update_stock'),
    path('ajax/bulk-update-stock/', views.bulk_update_stock, name='ajax_bulk_update_stock'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/download-check/', views.download_order_check_pdf, name='download_order_check'),
    path('orders/<int:order_id>/pay/', views.pay_order, name='pay_order'),
    path('checkout/', views.checkout, name='checkout'),
    path('order-complete/', views.order_complete, name='order_complete'),
    path('repair/', views.repair, name='repair'),  
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('terms-of-use/', views.terms_of_use, name='terms_of_use'),
    path('delivery/', views.delivery, name='delivery'),
    path('payment/', views.payment, name='payment'),
    path('warranty/', views.warranty, name='warranty'),
    path('ajax/review/vote/', views.review_helpful_vote, name='review_helpful_vote'),
    path('compare/', views.comparison_view, name='comparison'),
    path('ajax/compare/toggle/', views.toggle_compare, name='toggle_compare'),
    path('ajax/compare/clear/', views.clear_comparison, name='clear_comparison'),
    path('news/', views.news, name='news'),  
    path('news/<slug:slug>/', views.news_detail, name='news_detail'),
    path('useful-resources/', views.useful_resources, name='useful_resources'),
    path('feedback/', views.feedback, name='feedback'),
    path('registration/', views.registration, name='registration'),
    path('add-product/', views.add_product, name='add_product'),
    path('video/', views.videopost, name='video'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/favorites/', views.favorites_view, name='favorites'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('reorder/<int:order_id>/', views.reorder, name='reorder'),
    path('login/',
         LoginView.as_view
         (
             template_name='app/login.html',
             authentication_form=forms.BootstrapAuthenticationForm,
             extra_context=
             {
                 'title': 'Авторизация',
                 'year' : datetime.now().year,
             }
         ),
         name='login'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('password-reset/', PasswordResetView.as_view(
        form_class=SafePasswordResetForm,
        template_name='app/password_reset_form.html',
        email_template_name='app/password_reset_email.txt',
        html_email_template_name='app/password_reset_email.html',
        subject_template_name='app/password_reset_subject.txt',
    ), name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(
        template_name='app/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
        template_name='app/password_reset_confirm.html',
    ), name='password_reset_confirm'),
    path('password-reset/complete/', PasswordResetCompleteView.as_view(
        template_name='app/password_reset_complete.html',
    ), name='password_reset_complete'),
]
