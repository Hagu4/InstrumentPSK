
import re
path = 'DjangoWebProject1/settings.py'
with open(path, 'r') as f:
    content = f.read()
# Use a very simple string replace first to avoid regex issues
target = "ALLOWED_HOSTS = ['localhost', '127.0.0.1']"
replacement = "ALLOWED_HOSTS = ['*', 'instrumentpsk.ru', 'www.instrumentpsk.ru', '45.146.164.80']"
if target in content:
    content = content.replace(target, replacement)
else:
    # Fallback to a simpler regex if the string doesn't match exactly
    content = re.sub(r"ALLOWED_HOSTS\s*=\s*\[.*?\]", replacement, content)
with open(path, 'w') as f:
    f.write(content)
print('Settings updated.')
