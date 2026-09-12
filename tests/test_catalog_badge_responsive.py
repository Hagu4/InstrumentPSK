import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_CSS = ROOT / "DjangoWebProject1/app/static/app/css/catalog_redesign.css"


def find_browser():
    candidates = (
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    )
    return next((Path(path) for path in candidates if path and Path(path).is_file()), None)


class CatalogBadgeResponsiveTests(unittest.TestCase):
    browser = find_browser()

    def computed_badge_style(self, width, height):
        css_uri = CATALOG_CSS.resolve().as_uri()
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><link rel="stylesheet" href="{css_uri}"></head>
<body><div class="product-card-badges"><span id="badge" class="badge new">НОВИНКА</span></div>
<script>
const style = getComputedStyle(document.querySelector('#badge'));
document.body.dataset.result = JSON.stringify({{
  fontSize: style.fontSize,
  paddingTop: style.paddingTop,
  paddingRight: style.paddingRight
}});
</script></body></html>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "badge.html"
            browser_profile = Path(temp_dir) / "browser-profile"
            fixture.write_text(html, encoding="utf-8")
            result = subprocess.run(
                [
                    str(self.browser),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-sandbox",
                    f"--user-data-dir={browser_profile}",
                    f"--window-size={width},{height}",
                    "--dump-dom",
                    fixture.as_uri(),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        marker = 'data-result="'
        encoded = result.stdout.split(marker, 1)[1].split('"', 1)[0]
        return json.loads(encoded.replace("&quot;", '"'))

    @unittest.skipUnless(browser, "Edge or Chrome is required for responsive CSS checks")
    def test_badge_is_larger_on_small_desktop_monitor(self):
        style = self.computed_badge_style(1366, 768)
        self.assertEqual(style["fontSize"], "14px")
        self.assertEqual(style["paddingTop"], "5px")
        self.assertEqual(style["paddingRight"], "11px")

    @unittest.skipUnless(browser, "Edge or Chrome is required for responsive CSS checks")
    def test_badge_remains_compact_but_readable_on_mobile(self):
        style = self.computed_badge_style(390, 844)
        self.assertEqual(style["fontSize"], "13px")
        self.assertEqual(style["paddingTop"], "4px")
        self.assertEqual(style["paddingRight"], "9px")


if __name__ == "__main__":
    unittest.main()
