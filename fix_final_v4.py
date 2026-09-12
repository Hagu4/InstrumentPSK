
import re
path = 'DjangoWebProject1/settings.py'
with open(path, 'r') as f:
    content = f.read()
# Replace whatever ALLOWED_HOSTS is there with wildcard
content = re.sub(r"ALLOWED_HOSTS\s*=\s*\[.*?\]", "ALLOWED_HOSTS = ['*']", content)
with open(path, 'w') as f:
    f.write(content)
print('Fixed settings.py')
