"""One-time maintenance helper. Never prints credential values."""
import ast
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import shlex
import shutil
import re
import io
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')


import paramiko
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT.parent / 'InstrumentPSK-secure-release'
SOURCE = ROOT / '.worktrees/category-taxonomy'
VAULT = Path(os.environ['LOCALAPPDATA']) / 'InstrumentPSK-security'


def prepare():
    VAULT.mkdir(exist_ok=True)
    subprocess.run(['icacls', str(VAULT), '/inheritance:r', '/grant:r',
                    os.environ['USERNAME'] + ':(OI)(CI)F'], check=True, capture_output=True)
    credential_file = VAULT / 'rotation.json'
    if not credential_file.exists():
        tree = ast.parse((ROOT / 'auto_deploy_root.py').read_text(encoding='utf-8-sig'))
        values = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)}
        data = {'host': values['host'], 'user': values['user'],
                'old_ssh_password': values['password'],
                'new_ssh_password': secrets.token_urlsafe(48),
                'new_db_password': secrets.token_urlsafe(48),
                'new_django_key': secrets.token_urlsafe(64),
                'smtp_before': dotenv_values(SOURCE / 'DjangoWebProject1/.env').get('EMAIL_HOST_PASSWORD', '')}
        credential_file.write_text(json.dumps(data), encoding='utf-8')
    key_path = VAULT / 'id_instrumentpsk'
    if not key_path.exists():
        key = paramiko.RSAKey.generate(4096)
        key.write_private_key_file(str(key_path))
        key_path.with_suffix('.pub').write_text(key.get_name() + ' ' + key.get_base64() + ' instrumentpsk-maintenance\n')
    print('Protected rotation credentials and SSH key prepared outside repository.')


def connect():
    data = json.loads((VAULT / 'rotation.json').read_text())
    for attempt in range(3):
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
        auth = {'pkey': paramiko.RSAKey.from_private_key_file(str(VAULT / 'id_instrumentpsk'))} if (
            VAULT / 'key-installed').exists() else {'password': data['old_ssh_password']}
        try:
            ssh.connect(data['host'], username=data['user'], timeout=15, banner_timeout=15,
                        auth_timeout=15, allow_agent=False, look_for_keys=False, **auth)
            return ssh
        except (OSError, paramiko.SSHException):
            ssh.close()
            if attempt == 2: raise


def remote(command, input_data=None):
    ssh = connect()
    try:
        i, o, e = ssh.exec_command(command, timeout=180)
        if input_data:
            i.write(input_data)
            i.flush()
        i.channel.shutdown_write()
        out, err = o.read().decode('utf-8', 'replace'), e.read().decode('utf-8', 'replace')
        code = o.channel.recv_exit_status()
        # These commands must only emit deliberately non-secret diagnostics.
        print(out)
        if err:
            print(err)
        if code:
            raise RuntimeError('Remote command failed: ' + str(code))
    finally:
        ssh.close()


def configure_source():
    p = SOURCE / 'DjangoWebProject1/DjangoWebProject1/settings.py'
    text = p.read_text(encoding='utf-8')
    start = text.index('# SECURITY WARNING: keep the secret key')
    end = text.index('# Application references', start)
    text = text[:start] + 'from .security import *  # noqa: F403\n\n' + text[end:]
    text = text.replace('WHITENOISE_MANIFEST_STRICT = False\nWHITENOISE_MANIFEST_STRICT = False',
                        'WHITENOISE_MANIFEST_STRICT = False')
    p.write_text(text, encoding='utf-8')
    # Local keys are separate from the production key, and are not part of artifacts.
    for checkout in (ROOT, SOURCE):
        env_path = checkout / 'DjangoWebProject1/.env'
        text = env_path.read_text(encoding='utf-8-sig')
        import re
        text = re.sub(r'^SECRET_KEY=.*$', 'SECRET_KEY=' + secrets.token_urlsafe(64), text, flags=re.M)
        env_path.write_text(text, encoding='utf-8')
    print('Source settings updated; local Django keys rotated.')


def inspect_live():
    ssh = connect()
    try:
        i, o, e = ssh.exec_command('python3 -')
        i.write("""import pathlib,hashlib,json
root=pathlib.Path('/root/InstrumentPSK/DjangoWebProject1')
result={}
for folder in ('app','DjangoWebProject1'):
 for p in (root/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.html','.css','.js'):
   result[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(result))
""")
        i.channel.shutdown_write()
        live = json.loads(o.read().decode())
        changed = []
        for rel, digest in live.items():
            local = SOURCE / 'DjangoWebProject1' / rel
            if not local.exists() or hashlib.sha256(local.read_bytes()).hexdigest() != digest:
                changed.append(rel)
        print('Live source differences:', json.dumps(changed))
    finally:
        ssh.close()


def install_key():
    ssh = connect()
    try:
        sftp = ssh.open_sftp()
        try: sftp.mkdir('/root/.ssh', 0o700)
        except OSError: pass
        path = '/root/.ssh/authorized_keys'
        try:
            with sftp.open(path) as f: existing = f.read().decode()
        except FileNotFoundError: existing = ''
        public = (VAULT / 'id_instrumentpsk.pub').read_text().strip()
        if public not in existing:
            with sftp.open(path, 'w') as f: f.write(existing.rstrip() + '\n' + public + '\n')
        sftp.chmod(path, 0o600)
        sftp.close()
    finally: ssh.close()
    data = json.loads((VAULT / 'rotation.json').read_text())
    test = paramiko.SSHClient()
    test.load_system_host_keys()
    test.set_missing_host_key_policy(paramiko.RejectPolicy())
    test.connect(data['host'], username=data['user'],
                 pkey=paramiko.RSAKey.from_private_key_file(str(VAULT / 'id_instrumentpsk')),
                 allow_agent=False, look_for_keys=False, timeout=12)
    test.close()
    (VAULT / 'key-installed').write_text('verified')
    print('New SSH key installed and independently verified.')


def rotate_ssh():
    if not (VAULT / 'key-installed').exists(): raise RuntimeError('Verify key first')
    data = json.loads((VAULT / 'rotation.json').read_text())
    remote('chpasswd', 'root:' + data['new_ssh_password'] + '\n')
    (VAULT / 'ssh-rotated').write_text('done')
    print('Root password rotated; new password stored only in protected local vault.')


def prepare_release():
    if RELEASE.exists(): raise RuntimeError('Release destination already exists')
    RELEASE.mkdir()
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '.env*', '*.sqlite3', '*.zip',
                                    '*.pem', '*.key', 'media', 'staticfiles', '.git')
    for folder in ('app', 'DjangoWebProject1'):
        shutil.copytree(SOURCE / 'DjangoWebProject1' / folder,
                        RELEASE / 'DjangoWebProject1' / folder, ignore=ignore)
    shutil.copy2(SOURCE / 'DjangoWebProject1/manage.py', RELEASE / 'DjangoWebProject1/manage.py')
    for name in ('Dockerfile', 'docker-compose.yml', 'nginx.conf', 'requirements.txt', '.dockerignore'):
        shutil.copy2(SOURCE / name, RELEASE / name)
    shutil.copytree(SOURCE / 'tests', RELEASE / 'tests', ignore=ignore)
    (RELEASE / '.gitignore').write_text(
        '.env\n.env.*\n!.env.example\n*.zip\n*.tar\n*.gz\n*.sqlite3\n__pycache__/\n*.pyc\n'
        'media/\nstaticfiles/\n.venv/\n.security/\n', encoding='utf-8')
    with (RELEASE / '.dockerignore').open('a') as f:
        f.write('\n**/.env*\n**/*.zip\n**/*.key\n**/*.pem\n.git\n')
    ssh = connect()
    try:
        sftp = ssh.open_sftp()
        # Preserve the two live UI files that predate this security change.
        for rel in ('app/templates/app/404.html', 'app/static/app/scripts/_references.js'):
            sftp.get('/root/InstrumentPSK/DjangoWebProject1/' + rel,
                     str(RELEASE / 'DjangoWebProject1' / rel))
    finally: ssh.close()
    print('Release prepared at', RELEASE)


def snapshot_live():
    ssh = connect()
    try:
        sftp = ssh.open_sftp()
        backup = VAULT / 'before'
        backup.mkdir(exist_ok=True)
        for rel in ('docker-compose.yml', 'DjangoWebProject1/.env',
                    'DjangoWebProject1/DjangoWebProject1/settings.py'):
            target = backup / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists(): sftp.get('/root/InstrumentPSK/' + rel, str(target))
        i,o,e = ssh.exec_command("cd /root/InstrumentPSK && docker-compose exec -T web python -c " +
            shlex.quote("import os,json; print(json.dumps({'DATABASE_URL':os.environ['DATABASE_URL']}))"))
        data = json.loads(o.read().decode())
        (backup / 'database.json').write_text(json.dumps(data))
        if o.channel.recv_exit_status(): raise RuntimeError('Could not read database configuration')
    finally: ssh.close()
    remote('umask 077; mkdir -p /root/security-backup-20260912; '
           'cd /root/InstrumentPSK && docker-compose exec -T db sh -c '
           + shlex.quote('pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"')
           + ' > /root/security-backup-20260912/database.sql && '
           'test -s /root/security-backup-20260912/database.sql && echo DATABASE_BACKUP_OK')


def clean_history():
    mirror = VAULT / 'clean-history.git'
    if not mirror.exists():
        subprocess.run(['git', 'clone', '--mirror', '--no-hardlinks', str(ROOT), str(mirror)], check=True,
                       capture_output=True)
    history = subprocess.check_output(['git', '-C', str(ROOT), 'log', '-p', '--all', '--',
                                       '*.py', '*.env', '*.yml', '*.md', '*.txt']).decode('utf-8', 'replace')
    known = set()
    for match in re.finditer(r'''(?i)(?:password|passwd|pwd|secret_key|email_host_password)\s*(?:=|:)\s*(['"])([^'"\r\n]{4,})\1''', history):
        known.add(match.group(2))
    for checkout in (ROOT, SOURCE):
        values = dotenv_values(checkout / 'DjangoWebProject1/.env')
        for name in ('SECRET_KEY', 'EMAIL_HOST_PASSWORD'):
            if values.get(name): known.add(values[name])
    data = json.loads((VAULT / 'rotation.json').read_text())
    known.add(data['old_ssh_password'])
    known.add(data['smtp_before'])
    known.add('mypassword')
    # Historical unquoted .env values and settings fallback keys.
    for match in re.finditer(r'(?m)^\+?(?:SECRET_KEY|EMAIL_HOST_PASSWORD)=(.+)$', history):
        known.add(match.group(1).strip())
    known.discard('')
    (VAULT / 'known-secrets.json').write_text(json.dumps(sorted(known)))
    replacements = VAULT / 'replacements.txt'
    replacements.write_text(''.join('literal:' + value + '==>REMOVED_SECRET\n'
                                   for value in sorted(known) if '\n' not in value and '==>' not in value), encoding='utf-8')
    objects = subprocess.check_output(['git', '-C', str(mirror), 'rev-list', '--objects', '--all']).decode()
    drop = set()
    for line in objects.splitlines():
        if ' ' not in line: continue
        path = line.split(' ', 1)[1]
        parts = Path(path).parts
        if path.endswith('.py') and (len(parts) == 1 or
             (len(parts) == 2 and parts[0] == 'DjangoWebProject1' and parts[1] != 'manage.py')):
            drop.add(path)
    args = ['git', '-C', str(mirror), 'filter-repo', '--force', '--invert-paths',
            '--path-glob', '*.zip', '--path-glob', '*.sqlite3', '--path-glob', '*/.env',
            '--path', '.env', '--replace-text', str(replacements), '--replace-message', str(replacements)]
    for path in sorted(drop): args.extend(['--path', path])
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        print(result.stderr.decode('utf-8', 'replace'))
        raise RuntimeError('History filtering failed')
    subprocess.run(['git', '-C', str(RELEASE), 'init', '-b', 'release/production'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(RELEASE), 'fetch', str(mirror),
                    'refs/heads/feature/category-taxonomy'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(RELEASE), 'reset', '--mixed', 'FETCH_HEAD'], check=True, capture_output=True)
    # Working files are the allowlisted live release; removed legacy files stay removed.
    print('Historical secrets/scripts/archives removed in isolated history; release inherits sanitized history.')


def sanitize_legacy():
    from cryptography.fernet import Fernet
    keyfile = VAULT / 'quarantine.key'
    if not keyfile.exists(): keyfile.write_bytes(Fernet.generate_key())
    cipher = Fernet(keyfile.read_bytes())
    known = json.loads((VAULT / 'known-secrets.json').read_text())
    changed = 0
    archives = 0
    for checkout, label in ((ROOT, 'main'), (SOURCE, 'taxonomy')):
        names = subprocess.check_output(['git', '-C', str(checkout), 'ls-files', '-z']).decode().split('\0')
        for name in names:
            if not name: continue
            path = checkout / name
            if not path.is_file() or path.name.startswith('.env') or path.suffix.lower() not in ('.py', '.yml', '.yaml', '.md', '.txt', '.json'):
                continue
            try: text = path.read_text(encoding='utf-8-sig')
            except UnicodeDecodeError: continue
            updated = text
            for value in sorted(known, key=len, reverse=True):
                updated = updated.replace(value, 'REMOVED_SECRET')
            if updated != text:
                path.write_text(updated, encoding='utf-8')
                changed += 1
        # Deployment archives only, at the two known archive locations, never user media.
        for folder in (checkout, checkout / 'DjangoWebProject1'):
            for path in folder.glob('*.zip'):
                if 'deploy' not in path.name.lower(): continue
                target = VAULT / 'quarantine' / label / path.relative_to(checkout)
                target = target.with_suffix(target.suffix + '.encrypted')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(cipher.encrypt(path.read_bytes()))
                path.unlink()
                archives += 1
        # Keep runtime files locally while removing them from the index.
        tracked_secrets = [n for n in names if n and (Path(n).name == '.env' or n.endswith('.zip'))]
        if tracked_secrets:
            subprocess.run(['git', '-C', str(checkout), 'rm', '--cached', '--ignore-unmatch', '--', *tracked_secrets],
                           check=True, capture_output=True)
        ignore = checkout / '.gitignore'
        text = ignore.read_bytes().replace(b'\x00', b'').decode('utf-8-sig')
        text += '\n# Private runtime configuration and deployment artifacts\n.env\n.env.*\n!.env.example\n*.zip\n.worktrees/\nsecurity_maintenance.py\n'
        ignore.write_text(text, encoding='utf-8')
    print('Legacy text files sanitized:', changed, '; deployment archives encrypted/quarantined:', archives)


def stage_release():
    commit = subprocess.check_output(['git', '-C', str(RELEASE), 'rev-parse', 'HEAD']).decode().strip()
    archive = RELEASE.parent / 'InstrumentPSK-artifacts' / (commit + '.tar')
    if not archive.is_file(): raise RuntimeError('Build the clean commit artifact first')
    ssh = connect()
    try:
        sftp = ssh.open_sftp()
        sftp.put(str(archive), '/root/security-release.tar')
        sftp.chmod('/root/security-release.tar', 0o600)
    finally: ssh.close()
    stage = '/root/InstrumentPSK-security-' + commit[:7]
    remote('mkdir -p ' + stage + ' && tar -xf /root/security-release.tar -C ' + stage +
           ' && cd ' + stage + ' && docker build -t instrumentpsk-web:security-' + commit[:7] + ' .')
    (VAULT / 'built-commit').write_text(commit)


def prepare_production_env():
    from urllib.parse import urlsplit, urlunsplit, quote
    old = dotenv_values(VAULT / 'before/DjangoWebProject1/.env')
    data = json.loads((VAULT / 'rotation.json').read_text())
    database = json.loads((VAULT / 'before/database.json').read_text())['DATABASE_URL']
    url = urlsplit(database)
    if not re.fullmatch(r'[A-Za-z0-9_]+', url.username or ''):
        raise RuntimeError('Unexpected PostgreSQL role name')
    database_name = url.path.lstrip('/')
    netloc = quote(url.username) + ':' + data['new_db_password'] + '@' + (url.hostname or 'db')
    if url.port: netloc += ':' + str(url.port)
    old.update(DEBUG='False', SECRET_KEY=data['new_django_key'],
               ALLOWED_HOSTS='instrumentpsk.ru,www.instrumentpsk.ru',
               CSRF_TRUSTED_ORIGINS='https://instrumentpsk.ru,https://www.instrumentpsk.ru',
               SECURE_HSTS_SECONDS='3600',
               DATABASE_URL=urlunsplit((url.scheme, netloc, url.path, url.query, url.fragment)),
               EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    db_env = {'POSTGRES_DB': database_name, 'POSTGRES_USER': url.username,
              'POSTGRES_PASSWORD': data['new_db_password']}
    ssh = connect()
    try:
        sftp = ssh.open_sftp()
        for name, values in (('.env.security-next', old), ('.env.db.security-next', db_env)):
            path = '/root/InstrumentPSK/DjangoWebProject1/' + name
            with sftp.open(path, 'w') as f:
                if any('\n' in v or '\r' in v or '$' in v for v in values.values() if v is not None):
                    raise RuntimeError('Environment value needs explicit quoting')
                f.write(''.join(k + '=' + v + '\n' for k,v in values.items() if v is not None))
            sftp.chmod(path, 0o600)
    finally: ssh.close()
    commit = (VAULT / 'built-commit').read_text()
    remote('docker run --rm --env-file /root/InstrumentPSK/DjangoWebProject1/.env.security-next '
           'instrumentpsk-web:security-' + commit[:7] + ' python manage.py check --deploy')


def activate_release():
    from urllib.parse import urlsplit
    data = json.loads((VAULT / 'rotation.json').read_text())
    role = urlsplit(json.loads((VAULT / 'before/database.json').read_text())['DATABASE_URL']).username
    if not re.fullmatch(r'[A-Za-z0-9_]+', role): raise RuntimeError('Unexpected database role')
    commit = (VAULT / 'built-commit').read_text()
    remote('cd /root/InstrumentPSK && docker-compose stop web')
    remote('cd /root/InstrumentPSK && docker-compose exec -T db psql -v ON_ERROR_STOP=1 -U ' + role + ' -d postgres',
           'ALTER ROLE "' + role + '" WITH PASSWORD ' + "'" + data['new_db_password'] + "';\n")
    (VAULT / 'db-rotated').write_text('done')
    ssh = connect()
    try:
        sftp = ssh.open_sftp()
        base = '/root/InstrumentPSK/DjangoWebProject1/'
        sftp.posix_rename(base + '.env.security-next', base + '.env')
        sftp.posix_rename(base + '.env.db.security-next', base + '.env.db')
    finally: ssh.close()
    remote('tar -xf /root/security-release.tar -C /root/InstrumentPSK && '
           'docker tag instrumentpsk-web:security-' + commit[:7] + ' instrumentpsk-web:latest && '
           'cd /root/InstrumentPSK && docker-compose up -d --no-build db && '
           'for n in $(seq 1 30); do docker-compose exec -T db pg_isready -U ' + role +
           ' -d postgres >/dev/null && break; sleep 1; done && '
           'docker-compose exec -T db pg_isready -U ' + role + ' -d postgres && '
           'docker-compose up -d --no-build web && docker-compose exec -T nginx nginx -s reload')
    (VAULT / 'deployed-commit').write_text(commit)
    remote('cd /root/InstrumentPSK && docker-compose exec -T web python manage.py check --deploy && '
           'docker-compose ps && curl --max-time 20 -s -o /dev/null -w "HTTPS_STATUS=%{http_code}\\n" https://instrumentpsk.ru/')


def verify_live():
    data = json.loads((VAULT / 'rotation.json').read_text())
    code = '''import os, json, smtplib
os.environ.setdefault('DJANGO_SETTINGS_MODULE','DjangoWebProject1.settings')
import django; django.setup()
from django.conf import settings
from django.db import connection
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from unittest.mock import patch
with connection.cursor() as cursor:
 cursor.execute('SELECT 1'); assert cursor.fetchone()[0] == 1
print('DATABASE_CONNECTION_OK')
assert not settings.DEBUG
assert settings.SECURE_SSL_REDIRECT and settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
assert settings.SECRET_KEY == EXPECTED_KEY
print('PRODUCTION_SECURITY_OK')
client=Client(HTTP_HOST='instrumentpsk.ru')
email=get_user_model().objects.filter(is_active=True).exclude(email='').values_list('email',flat=True).first()
with override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'):
 with patch('django.core.mail.EmailMultiAlternatives.send',side_effect=smtplib.SMTPAuthenticationError(535,b'test failure')):
  response=client.post('/password-reset/',{'email':email},secure=True)
  assert response.status_code == 302 and response.url == '/password-reset/done/'
print('SMTP_ERROR_HANDLING_OK')
assert client.get('/',secure=True).status_code == 200
assert client.get('/catalog/',secure=True).status_code == 200
print('HOME_AND_CATALOG_OK')
with smtplib.SMTP(settings.EMAIL_HOST,settings.EMAIL_PORT,timeout=10) as smtp:
 smtp.starttls(); smtp.login(settings.EMAIL_HOST_USER,settings.EMAIL_HOST_PASSWORD)
print('CURRENT_SMTP_LOGIN_OK_NO_EMAIL_SENT')
'''.replace('EXPECTED_KEY', repr(data['new_django_key']))
    remote('cd /root/InstrumentPSK && docker-compose exec -T web python -', code)
    remote("docker inspect instrumentpsk-db-1 --format='{{json .HostConfig.PortBindings}}' && "
           "curl --max-time 20 -sI https://instrumentpsk.ru/password-reset/ | head -n 16")


def adopt_clean_history():
    backup = VAULT / 'original-git-recovery'
    if not backup.exists(): shutil.copytree(ROOT / '.git', backup)
    mirror = VAULT / 'clean-history.git'
    subprocess.run(['git', '-C', str(ROOT), 'fetch', '--update-head-ok', str(mirror),
                    '+refs/*:refs/*'], check=True, capture_output=True)
    clean_refs = set(subprocess.check_output(['git', '-C', str(mirror), 'for-each-ref', '--format=%(refname)']).decode().splitlines())
    current_refs = set(subprocess.check_output(['git', '-C', str(ROOT), 'for-each-ref', '--format=%(refname)']).decode().splitlines())
    for ref in current_refs - clean_refs:
        if not ref.startswith('refs/remotes/'):
            raise RuntimeError('Unexpected extra local reference; preserve and inspect: ' + ref)
        subprocess.run(['git', '-C', str(ROOT), 'update-ref', '-d', ref], check=True)
    # Mixed resets refresh indexes only. Both working directories and uncommitted edits survive.
    for checkout in (ROOT, SOURCE):
        subprocess.run(['git', '-C', str(checkout), 'reset', '--mixed', 'HEAD'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(ROOT), 'reflog', 'expire', '--expire=now', '--all'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(ROOT), 'gc', '--prune=now'], check=True, capture_output=True)
    print('Original local branch histories sanitized; working files preserved; protected recovery copy outside Git.')


def rotate_exposed_app_passwords():
    known = set(json.loads((VAULT / 'known-secrets.json').read_text()))
    # Older administrative utilities also used unquoted shell environment values.
    for checkout in (ROOT, SOURCE):
        for p in checkout.glob('*.py'):
            if p.name == 'security_maintenance.py': continue
            text = p.read_text(encoding='utf-8-sig', errors='replace')
            for match in re.finditer(r'DJANGO_SUPERUSER_PASSWORD=([^\s\'";]+)', text):
                known.add(match.group(1))
            for match in re.finditer(r'''set_password\(['"]([^'"]+)['"]\)''', text):
                known.add(match.group(1))
    known.discard('REMOVED_SECRET')
    (VAULT / 'known-secrets.json').write_text(json.dumps(sorted(known)))
    code = '''import os,json,secrets
os.environ.setdefault('DJANGO_SETTINGS_MODULE','DjangoWebProject1.settings')
import django; django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
result=[]
with transaction.atomic():
 for user in get_user_model().objects.select_for_update().filter(is_staff=True):
  if any(user.check_password(candidate) for candidate in CANDIDATES):
   password=secrets.token_urlsafe(48)
   user.set_password(password); user.save(update_fields=['password'])
   result.append({'username':user.get_username(),'password':password})
print(json.dumps(result))
'''.replace('CANDIDATES', repr(sorted(known)))
    ssh = connect()
    try:
        i,o,e = ssh.exec_command('cd /root/InstrumentPSK && docker-compose exec -T web python -')
        i.write(code); i.channel.shutdown_write()
        result = json.loads(o.read().decode())
        if o.channel.recv_exit_status(): raise RuntimeError('Administrative password rotation failed')
        (VAULT / 'rotated-app-accounts.json').write_text(json.dumps(result))
        print('Exposed application administrator passwords rotated:', len(result))
    finally: ssh.close()
    # Remove any additional administrative password literals from remaining utility files.
    for checkout in (ROOT, SOURCE):
        for p in checkout.glob('*.py'):
            if p.name == 'security_maintenance.py': continue
            text = p.read_text(encoding='utf-8-sig', errors='replace')
            result = text
            for value in sorted(known, key=len, reverse=True): result = result.replace(value, 'REMOVED_SECRET')
            if result != text: p.write_text(result, encoding='utf-8')


def clean_server_artifacts():
    from cryptography.fernet import Fernet
    cipher = Fernet((VAULT / 'quarantine.key').read_bytes())
    known = json.loads((VAULT / 'known-secrets.json').read_text())
    ssh = connect()
    count = 0
    cleaned = 0
    try:
        sftp = ssh.open_sftp()
        for folder in ('/root', '/root/InstrumentPSK', '/root/InstrumentPSK/DjangoWebProject1'):
            for attr in sftp.listdir_attr(folder):
                name = attr.filename
                if '/' in name: raise RuntimeError('Unexpected filename')
                path = folder + '/' + name
                if name.endswith('.zip') and 'deploy' in name.lower():
                    with sftp.open(path, 'rb') as f:
                        f.prefetch(attr.st_size, max_concurrent_requests=32)
                        content = f.read()
                    destination = VAULT / 'quarantine/server' / path.lstrip('/')
                    destination = destination.with_suffix('.zip.encrypted')
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(cipher.encrypt(content))
                    sftp.remove(path)
                    count += 1
                elif name.endswith(('.py', '.yml', '.yaml', '.txt', '.json')) and name != 'settings.py':
                    with sftp.open(path, 'rb') as f: original = f.read()
                    try: text = original.decode('utf-8')
                    except UnicodeDecodeError: continue
                    updated = text
                    for value in sorted(known, key=len, reverse=True): updated = updated.replace(value, 'REMOVED_SECRET')
                    if updated != text:
                        with sftp.open(path, 'w') as f: f.write(updated)
                        cleaned += 1
        sftp.close()
    finally: ssh.close()
    print('Server deployment archives encrypted/quarantined:', count, '; legacy text files sanitized:', cleaned)


def guard_legacy_entrypoints():
    for checkout in (ROOT, SOURCE):
        for rel in ('create_zip_root.py', 'DjangoWebProject1/create_zip.py',
                    'DjangoWebProject1/create_deployment_package.py'):
            path = checkout / rel
            if not path.exists(): continue
            path.write_text('"""Deprecated: deployment artifacts must come from a clean release commit."""\n'
                            'raise SystemExit("Use InstrumentPSK-secure-release/build_release.py; '
                            'whole-directory archives may expose secrets.")\n', encoding='utf-8')
    # Align common infrastructure defaults in both older checkouts as a safeguard.
    for checkout in (ROOT, SOURCE):
        for rel in ('docker-compose.yml', '.dockerignore', 'Dockerfile',
                    'DjangoWebProject1/DjangoWebProject1/security.py'):
            shutil.copy2(RELEASE / rel, checkout / rel)
        path = checkout / 'DjangoWebProject1/DjangoWebProject1/settings.py'
        text = path.read_text(encoding='utf-8')
        if '# SECURITY WARNING: keep the secret key' in text:
            start = text.index('# SECURITY WARNING: keep the secret key')
            end = text.index('# Application references', start)
            text = text[:start] + 'from .security import *  # noqa: F403\n\n' + text[end:]
            path.write_text(text, encoding='utf-8')
    print('Legacy archive builders disabled; security defaults aligned across local checkouts.')


def scan_history():
    values = json.loads((VAULT / 'known-secrets.json').read_text())
    # The regex source in this helper was initially picked up as an unquoted assignment.
    values = [v for v in values if not v.startswith('([^')]
    (VAULT / 'known-secrets.json').write_text(json.dumps(values))
    known = [v.encode() for v in values]
    for repo in (ROOT, RELEASE):
        objects = subprocess.check_output(['git', '-C', str(repo), 'rev-list', '--objects', '--all']).decode().splitlines()
        private = []
        text_objects = {}
        for line in objects:
            if ' ' not in line: continue
            oid, name = line.split(' ', 1)
            path = Path(name)
            if path.name == '.env' or path.suffix == '.zip': private.append(name)
            if path.suffix in ('.py','.txt','.md','.json','.yml','.yaml','.html','.js','.ini') or path.name == '.env.example':
                text_objects[oid] = name
        found = []
        process = subprocess.Popen(['git', '-C', str(repo), 'cat-file', '--batch'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        for oid, name in text_objects.items():
            process.stdin.write((oid + '\n').encode()); process.stdin.flush()
            header = process.stdout.readline().split()
            size = int(header[2])
            content = process.stdout.read(size); process.stdout.read(1)
            if any(value in content for value in known): found.append(name)
        process.stdin.close(); process.wait()
        print(repo.name, 'private history paths:', len(private), 'known-secret text blobs:', len(found))
        if private or found:
            print('Affected paths only:', sorted(set(private + found)))
            raise RuntimeError('History still needs cleanup')


def final_checks():
    old_url = json.loads((VAULT / 'before/database.json').read_text())['DATABASE_URL']
    code = '''import psycopg2
try:
 connection=psycopg2.connect(OLD_URL,connect_timeout=5)
except psycopg2.OperationalError:
 print('OLD_DATABASE_CREDENTIALS_REJECTED')
else:
 connection.close()
 raise RuntimeError('Old database credentials still work')
'''.replace('OLD_URL', repr(old_url))
    remote('cd /root/InstrumentPSK && docker-compose exec -T web python -', code)
    commit = (VAULT / 'deployed-commit').read_text()
    ssh = connect()
    try:
        sftp = ssh.open_sftp()
        with sftp.open('/root/InstrumentPSK/DEPLOYED_COMMIT', 'w') as f: f.write(commit + '\n')
    finally: ssh.close()
    remote("stat -c '%a %n' /root/InstrumentPSK/DjangoWebProject1/.env /root/InstrumentPSK/DjangoWebProject1/.env.db && "
           "curl --max-time 20 -s -o /dev/null -w 'HOME=%{http_code}\\n' https://instrumentpsk.ru/ && "
           "curl --max-time 20 -s -o /dev/null -w 'RESET=%{http_code}\\n' https://instrumentpsk.ru/password-reset/ && "
           "docker inspect instrumentpsk-db-1 --format='DB_PUBLISHED_PORTS={{json .HostConfig.PortBindings}}'")


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'prepare': prepare()
    elif action == 'configure-source': configure_source()
    elif action == 'remote': remote(sys.argv[2])
    elif action == 'inspect-live': inspect_live()
    elif action == 'install-key': install_key()
    elif action == 'rotate-ssh': rotate_ssh()
    elif action == 'prepare-release': prepare_release()
    elif action == 'snapshot-live': snapshot_live()
    elif action == 'clean-history': clean_history()
    elif action == 'sanitize-legacy': sanitize_legacy()
    elif action == 'stage-release': stage_release()
    elif action == 'prepare-production-env': prepare_production_env()
    elif action == 'activate-release': activate_release()
    elif action == 'verify-live': verify_live()
    elif action == 'adopt-clean-history': adopt_clean_history()
    elif action == 'rotate-app-passwords': rotate_exposed_app_passwords()
    elif action == 'clean-server-artifacts': clean_server_artifacts()
    elif action == 'guard-legacy-entrypoints': guard_legacy_entrypoints()
    elif action == 'scan-history': scan_history()
    elif action == 'final-checks': final_checks()
    elif action == 'confirm-stage':
        commit = subprocess.check_output(['git', '-C', str(RELEASE), 'rev-parse', 'HEAD']).decode().strip()
        remote('docker image inspect instrumentpsk-web:security-' + commit[:7] + ' --format={{.Id}}')
        (VAULT / 'built-commit').write_text(commit)
