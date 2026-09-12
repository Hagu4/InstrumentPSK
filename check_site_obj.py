from django.contrib.sites.models import Site
for site in Site.objects.all():
    print(f"ID: {site.id}, Domain: {site.domain}")
