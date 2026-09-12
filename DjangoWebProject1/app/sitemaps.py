from django.contrib.sitemaps import Sitemap
from .models import Product, Category
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return ['home', 'catalog', 'contact', 'about', 'useful_resources']

    def location(self, item):
        return reverse(item)

class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Category.objects.all()

class ProductSitemap(Sitemap):
    changefreq = "daily"
    priority = 1.0

    def items(self):
        return Product.objects.all()
