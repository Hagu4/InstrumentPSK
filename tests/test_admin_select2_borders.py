import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADMIN_CSS = ROOT / "DjangoWebProject1/app/static/app/css/admin_custom_v4.css"


def find_browser():
    candidates = (
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    )
    return next((Path(path) for path in candidates if path and Path(path).is_file()), None)


class AdminSelect2BorderTests(unittest.TestCase):
    browser = find_browser()

    @unittest.skipUnless(browser, "Edge or Chrome is required for CSS checks")
    def test_autocomplete_select_has_visible_border_after_select2_loads(self):
        css_uri = ADMIN_CSS.resolve().as_uri()
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><link rel="stylesheet" href="{css_uri}"></head>
<body class="app-app model-product change-form">
<div style="width: 800px"><input id="id_title" type="text" class="vTextField" value="Дровокол"></div>
<input id="price" type="number" class="vIntegerField" value="22990">
<select id="author"><option>---------</option></select>
<textarea id="description">Описание</textarea>
<span class="select2-container select2-container--admin-autocomplete">
<span id="selection" class="select2-selection select2-selection--single">
  <span class="select2-selection__rendered">VILLARTEC</span>
  <button id="clear" class="select2-selection__clear" type="button">×</button>
  <span class="select2-selection__arrow"><b id="arrow"></b></span>
</span>
</span><script>
const style = getComputedStyle(document.querySelector('#selection'));
const arrow = getComputedStyle(document.querySelector('#arrow'));
const clear = getComputedStyle(document.querySelector('#clear'));
const fieldIds = ['id_title', 'price', 'author', 'description'];
const fields = Object.fromEntries(fieldIds.map(id => {{
  const fieldStyle = getComputedStyle(document.querySelector('#' + id));
  return [id, {{
    borderTopWidth: fieldStyle.borderTopWidth,
    borderRightWidth: fieldStyle.borderRightWidth,
    borderBottomWidth: fieldStyle.borderBottomWidth,
    borderLeftWidth: fieldStyle.borderLeftWidth,
    borderColor: fieldStyle.borderTopColor,
    borderRadius: fieldStyle.borderRadius,
    width: fieldStyle.width
  }}];
}}));
document.body.dataset.result = JSON.stringify({{
  borderColor: style.borderTopColor,
  borderWidth: style.borderTopWidth,
  borderStyle: style.borderTopStyle,
  arrowWidth: arrow.width,
  arrowBorderRightWidth: arrow.borderRightWidth,
  arrowBorderBottomWidth: arrow.borderBottomWidth,
  clearWidth: clear.width,
  clearHeight: clear.height,
  clearBorderRadius: clear.borderRadius,
  fields
}});
</script></body></html>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "admin-select2.html"
            profile = Path(temp_dir) / "browser-profile"
            fixture.write_text(html, encoding="utf-8")
            result = subprocess.run(
                [
                    str(self.browser),
                    "--headless=new",
                    "--disable-gpu",
                    "--no-first-run",
                    "--no-sandbox",
                    f"--user-data-dir={profile}",
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
        style = json.loads(encoded.replace("&quot;", '"'))
        self.assertEqual(style["borderWidth"], "2px")
        self.assertEqual(style["borderStyle"], "solid")
        self.assertEqual(style["borderColor"], "rgb(148, 163, 184)")
        self.assertEqual(style["arrowWidth"], "9px")
        self.assertEqual(style["arrowBorderRightWidth"], "2px")
        self.assertEqual(style["arrowBorderBottomWidth"], "2px")
        self.assertEqual(style["clearWidth"], "24px")
        self.assertEqual(style["clearHeight"], "24px")
        self.assertEqual(style["clearBorderRadius"], "50%")
        for field_name in ("id_title", "price", "author", "description"):
            with self.subTest(field=field_name):
                field = style["fields"][field_name]
                self.assertEqual(
                    [field[side] for side in (
                        "borderTopWidth",
                        "borderRightWidth",
                        "borderBottomWidth",
                        "borderLeftWidth",
                    )],
                    ["2px", "2px", "2px", "2px"],
                )
                self.assertEqual(field["borderColor"], "rgb(148, 163, 184)")
                self.assertEqual(field["borderRadius"], "12px")
        self.assertEqual(style["fields"]["id_title"].get("width"), "720px")


if __name__ == "__main__":
    unittest.main()
