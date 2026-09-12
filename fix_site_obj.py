from django.contrib.sites.models import Site
site, created = Site.objects.get_or_create(id=1, defaults={'domain': 'instrumentpsk.ru', 'name': 'InstrumentPSK'})
if not created:
    site.domain = 'instrumentpsk.ru'
    site.name = 'InstrumentPSK'
    site.save()
print(f"Site configured: ID={site.id}, Domain={site.domain}")
