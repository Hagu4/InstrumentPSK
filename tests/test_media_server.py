"""Exercise the production media location in a disposable Nginx container."""
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request


@unittest.skipUnless(os.environ.get('RUN_NGINX_TESTS') == '1', 'Requires Docker; enabled in CI')
class MediaServerTests(unittest.TestCase):
    def test_media_allows_images_and_blocks_active_documents(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='instrumentpsk-nginx-') as directory:
            fixtures = Path(directory)
            certificate = fixtures / 'certificate'
            media = fixtures / 'media'
            certificate.mkdir()
            media.mkdir()
            (media / 'image.png').write_bytes(b'fixture image bytes')
            (media / 'document.html').write_text('<title>Blocked document</title>', encoding='utf-8')
            (media / 'document.svg').write_text('<svg></svg>', encoding='utf-8')
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                '-keyout', str(certificate / 'privkey.pem'), '-out', str(certificate / 'fullchain.pem'),
                '-days', '1', '-subj', '/CN=localhost'], check=True, capture_output=True, timeout=30)
            command = ['docker', 'run', '--rm', '-d', '--add-host', 'web:127.0.0.1',
                '-p', '127.0.0.1::443',
                '-v', f'{root / "nginx.conf"}:/etc/nginx/conf.d/default.conf:ro',
                '-v', f'{certificate}:/etc/letsencrypt/live/instrumentpsk.ru:ro',
                '-v', f'{media}:/app/media:ro', 'nginx:1.25-alpine']
            container = subprocess.check_output(command, text=True, timeout=120).strip()
            try:
                subprocess.run(['docker', 'exec', container, 'nginx', '-t'], check=True, capture_output=True, timeout=30)
                port = subprocess.check_output(['docker', 'port', container, '443/tcp'], text=True, timeout=10).strip().rsplit(':', 1)[1]
                # This disposable server deliberately uses a self-signed certificate.
                context = ssl._create_unverified_context()
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
                url = f'https://127.0.0.1:{port}/media/'
                for attempt in range(30):
                    try:
                        response = opener.open(url + 'image.png', timeout=2)
                        break
                    except urllib.error.URLError:
                        if attempt == 29:
                            raise
                        time.sleep(0.1)
                with response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                    self.assertIn('sandbox', response.headers['Content-Security-Policy'])
                for name in ['document.html', 'document.svg']:
                    with self.subTest(name=name), self.assertRaises(urllib.error.HTTPError) as failure:
                        opener.open(url + name, timeout=5)
                    self.assertEqual(failure.exception.code, 404)
            finally:
                subprocess.run(['docker', 'stop', container], check=True, capture_output=True, timeout=30)
