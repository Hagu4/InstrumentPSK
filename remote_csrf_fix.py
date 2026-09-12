
path = 'DjangoWebProject1/settings.py'
with open(path, 'r') as f:
    content = f.read()

csrf_setting = "\nCSRF_TRUSTED_ORIGINS = ['https://instrumentpsk.ru', 'https://www.instrumentpsk.ru']\n"

if 'CSRF_TRUSTED_ORIGINS' not in content:
    with open(path, 'a') as f_out:
        f_out.write(csrf_setting)
    print('CSRF_TRUSTED_ORIGINS added.')
else:
    print('CSRF_TRUSTED_ORIGINS already exists, manual check might be needed if it still fails.')
