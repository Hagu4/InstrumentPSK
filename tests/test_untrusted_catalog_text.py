"""Run the real UI scripts with untrusted API strings in a headless browser."""
import html
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_admin_select2_borders import find_browser

ROOT = Path(__file__).resolve().parents[1] / 'DjangoWebProject1/app'


@unittest.skipUnless(find_browser(), 'Edge or Chrome is required')
class UntrustedCatalogTextTests(unittest.TestCase):
    def test_api_text_and_toast_title_are_never_interpreted_as_html(self):
        marker = '<img data-injected src=x onerror="window.auditInjected=true">'
        layout = (ROOT / 'templates/app/layout.html').read_text(encoding='utf-8')
        toast = layout.split('window.showToast =', 1)[1].split("document.addEventListener('DOMContentLoaded'", 1)[0]
        page = '''<!doctype html><meta charset="utf-8">
<form class="search-container" data-search-url="/live-search/">
<input id="search-input"><div id="search-results"></div><span class="spinner"></span></form>
<div id="toast-container"></div>
<button class="quick-view-btn" data-product-id="1">Open</button>
<div class="modal-overlay"><div class="modal-content">
<button class="modal-close"></button><img class="modal-product-image">
<div class="modal-img-nav"></div><a class="modal-brand"></a><span class="modal-name"></span>
<div class="modal-rating"><span class="reviews-count"></span></div>
<div class="modal-specs-grid"></div><div class="modal-current-price"></div><div class="modal-old-price"></div>
<div class="modal-discount-percent"></div><button class="modal-add-btn"></button>
<button class="modal-favorite-btn"></button><div class="modal-desc"></div></div></div>
<script>window.auditInjected=false; const marker=__MARKER__;
window.fetch = async (url) => ({ok:true, json:async () => url.startsWith('/live-search/') ?
 [{id:1, name:marker, url:'/product/1/', image_url:'', category:marker, brand:marker, sku:marker, matched_chars:[marker]}] :
 {id:1, title:marker, brand:marker, brand_url:'/catalog/', images:[], image_url:'',
 features:[{name:marker,value:marker}], price:'100', old_price:null, average_rating:0,
 review_count:0, in_stock:true, is_favorited:false, detail_url:'/product/1/'} });
window.showToast = __TOAST__
</script>
<script src="__SEARCH__"></script><script src="__QUICK__"></script>
<script>document.addEventListener('DOMContentLoaded', () => {
 const input=document.querySelector('#search-input'); input.value='tool'; input.dispatchEvent(new Event('input'));
 document.querySelector('.quick-view-btn').click();
 window.showToast(marker, 'success', marker);
 setTimeout(() => { document.body.dataset.result=JSON.stringify({
  injected:window.auditInjected, injectedElements:document.querySelectorAll('[data-injected]').length,
  search:document.querySelector('.item-name')?.textContent,
  spec:document.querySelector('.modal-spec-value')?.textContent,
  toast:document.querySelector('.product-title')?.textContent
 }); }, 700);
});</script>'''
        page = (page.replace('__MARKER__', json.dumps(marker))
                .replace('__TOAST__', toast)
                .replace('__SEARCH__', (ROOT / 'static/app/js/live_search.js').as_uri())
                .replace('__QUICK__', (ROOT / 'static/app/js/quick-view.js').as_uri()))
        with tempfile.TemporaryDirectory(prefix='instrumentpsk-dom-') as directory:
            fixture = Path(directory) / 'test.html'
            fixture.write_text(page, encoding='utf-8')
            result = subprocess.run([str(find_browser()), '--headless=new', '--disable-gpu',
                '--no-sandbox', '--no-first-run', '--virtual-time-budget=1200',
                f'--user-data-dir={Path(directory) / "profile"}', '--dump-dom', fixture.as_uri()],
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=30)
        encoded = result.stdout.split('data-result="', 1)[1].split('"', 1)[0]
        observed = json.loads(html.unescape(encoded))
        self.assertFalse(observed['injected'])
        self.assertEqual(observed['injectedElements'], 0)
        for field in ['search', 'spec', 'toast']:
            self.assertEqual(observed[field], marker)
