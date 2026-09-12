import os
import django
from django.template import Template, Context

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoWebProject1.settings')
django.setup()

try:
    t = Template("{% load app_filters %}{{ 42200|format_price }}")
    c = Context({})
    print("Rendered:", t.render(c))
except Exception as e:
    print("Error during rendering:", e)
    import traceback
    traceback.print_exc()
