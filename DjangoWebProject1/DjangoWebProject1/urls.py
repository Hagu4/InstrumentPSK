from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
import os # <-- Added this import

from django.contrib.sitemaps.views import sitemap
from app.sitemaps import StaticViewSitemap, CategorySitemap, ProductSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'categories': CategorySitemap,
    'products': ProductSitemap,
}

urlpatterns = [
    path('management-psk-zone/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('', include('app.urls')), 
] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Add this line to serve static files explicitly from STATICFILES_DIRS
    urlpatterns += static(settings.STATIC_URL, document_root=os.path.join(settings.BASE_DIR, 'app/static'))

handler404 = 'app.views.custom_404_view'
handler500 = 'app.views.custom_500_view'
