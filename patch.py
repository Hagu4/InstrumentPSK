import sys

file_path = '/root/app/DjangoWebProject1/DjangoWebProject1/settings.py'

# Read all lines
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Filter out bad lines
lines = [line for line in lines if 'x27HTTP_X_FORWARDED_PROTOx27' not in line]

# Append the correct setting
lines.append("\nSECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')\n")

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Patch applied successfully.")
