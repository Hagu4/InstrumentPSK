import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_CSS = ROOT / "DjangoWebProject1/app/static/app/css/catalog_redesign.css"
CATALOG_TEMPLATE = ROOT / "DjangoWebProject1/app/templates/app/catalog.html"


def find_browser():
    candidates = (
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    )
    return next((Path(path) for path in candidates if path and Path(path).is_file()), None)


class NestedCategoryLayoutTests(unittest.TestCase):
    browser = find_browser()

    def nested_toggle_script(self):
        template = CATALOG_TEMPLATE.read_text(encoding="utf-8")
        start = template.index("document.querySelectorAll('.has-nested-subcategories")
        end = template.index("// Mobile Filters Toggle", start)
        return template[start:end]

    def render_state(
        self,
        width=1200,
        extra_group_class="",
        focus_link=False,
        toggle_clicks=0,
        reduced_motion=False,
        large_grid=False,
        panel_width=500,
    ):
        css = CATALOG_CSS.read_text(encoding="utf-8")
        focus_script = "document.querySelector('#parent-link').focus();" if focus_link else ""
        click_script = "\n".join(
            "document.querySelector('#nested-toggle').click();"
            for _ in range(toggle_clicks)
        )
        toggle_script = self.nested_toggle_script()
        grid_class = " subcategory-grid-large" if large_grid else ""
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><style>{css}</style></head>
<body>
  <div class="sidebar-categories" style="width: {panel_width}px">
    <div class="subcategory-grid{grid_class}">
      <div id="short-group" class="sub-item-group">
        <div class="sub-item-row">
          <a class="sub-item" href="#first">
            <span class="sub-item-name">Ключи</span>
            <span class="sub-item-count">8</span>
          </a>
        </div>
      </div>
      <div id="long-group" class="sub-item-group">
        <div class="sub-item-row">
          <a class="sub-item" href="#long">
            <span id="long-name" class="sub-item-name">Отвёртки, биты и наборы для точных монтажных работ</span>
            <span id="long-count" class="sub-item-count">128</span>
          </a>
        </div>
      </div>
      <div id="other-group" class="sub-item-group has-nested-subcategories nested-open">
        <div class="sub-item-row">
          <a class="sub-item" href="#other">Другая</a>
          <button id="other-toggle" class="nested-subcategory-toggle" type="button" aria-expanded="true" aria-controls="other-nested"><span class="nested-subcategory-chevron">Открыть</span></button>
        </div>
        <div id="other-nested" class="nested-subcategory-list"><a class="nested-subcategory-item" href="#other-child">Другая вложенная</a></div>
      </div>
      <div class="sub-item-group has-nested-subcategories {extra_group_class}">
        <div class="sub-item-row">
          <a id="parent-link" class="sub-item" href="#parent">Цепные пилы</a>
          <button id="nested-toggle" class="nested-subcategory-toggle" type="button" aria-expanded="false" aria-controls="nested"><span class="nested-subcategory-chevron">Открыть</span></button>
        </div>
        <div id="nested" class="nested-subcategory-list">
          <a class="nested-subcategory-item" href="#battery">Аккумуляторные</a>
          <a class="nested-subcategory-item" href="#petrol">Бензиновые</a>
          <a class="nested-subcategory-item" href="#electric">Электрические</a>
        </div>
      </div>
    </div>
  </div>
  <a id="child-tile" class="category-child-tile" href="#child">Child tile</a>
  <script>
    const expandedBeforeClick = document.querySelector('#nested-toggle').getAttribute('aria-expanded');
    {toggle_script}
    {focus_script}
    {click_script}
    function countActiveNestedHoverRules(rules) {{
      return [...rules].reduce((count, rule) => {{
        if (rule.type === CSSRule.MEDIA_RULE) {{
          return count + (matchMedia(rule.conditionText).matches
            ? countActiveNestedHoverRules(rule.cssRules)
            : 0);
        }}
        return count + (rule.selectorText?.includes('.has-nested-subcategories:hover .nested-subcategory-list') ? 1 : 0);
      }}, 0);
    }}
    const group = document.querySelector('.has-nested-subcategories:last-child');
    const grid = document.querySelector('.subcategory-grid');
    const shortRow = document.querySelector('#short-group .sub-item-row').getBoundingClientRect();
    const longRow = document.querySelector('#long-group .sub-item-row').getBoundingClientRect();
    const parentRow = group.querySelector('.sub-item-row').getBoundingClientRect();
    const longName = document.querySelector('#long-name').getBoundingClientRect();
    const longCount = document.querySelector('#long-count').getBoundingClientRect();
    const nestedList = document.querySelector('#nested').getBoundingClientRect();
    const nestedItems = [...document.querySelectorAll('#nested .nested-subcategory-item')];
    const nestedItemRects = nestedItems.map(item => item.getBoundingClientRect());
    document.body.dataset.result = JSON.stringify({{
      nestedDisplay: getComputedStyle(document.querySelector('#nested')).display,
      nestedPosition: getComputedStyle(document.querySelector('#nested')).position,
      gridColumns: getComputedStyle(grid).gridTemplateColumns.split(' ').length,
      groupWidth: group.getBoundingClientRect().width,
      regularTileWidth: document.querySelector('#short-group').getBoundingClientRect().width,
      gridInnerWidth: grid.clientWidth - 28,
      regularRowHeights: [shortRow.height, longRow.height],
      parentRowHeight: parentRow.height,
      longNameCountGap: longCount.left - longName.right,
      longNameInsideRow: longName.bottom <= longRow.bottom + 0.5,
      toggleSize: [
        document.querySelector('#nested-toggle').getBoundingClientRect().width,
        document.querySelector('#nested-toggle').getBoundingClientRect().height
      ],
      nestedListInsets: [
        nestedList.left - group.getBoundingClientRect().left,
        group.getBoundingClientRect().right - nestedList.right
      ],
      nestedItemHeights: nestedItemRects.map(rect => rect.height),
      nestedItemTops: nestedItemRects.map(rect => rect.top),
      motionDurations: [
        getComputedStyle(document.querySelector('#short-group .sub-item')).transitionDuration,
        getComputedStyle(document.querySelector('#nested-toggle .nested-subcategory-chevron')).transitionDuration,
        getComputedStyle(document.querySelector('#child-tile')).transitionDuration
      ],
      expandedBeforeClick,
      expandedAfterClick: document.querySelector('#nested-toggle').getAttribute('aria-expanded'),
      otherGroupOpen: document.querySelector('#other-group').classList.contains('nested-open'),
      otherExpanded: document.querySelector('#other-toggle').getAttribute('aria-expanded'),
      activeNestedHoverRules: countActiveNestedHoverRules(document.styleSheets[0].cssRules)
    }});
  </script>
</body></html>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "nested-category.html"
            browser_profile = Path(temp_dir) / "browser-profile"
            fixture.write_text(html, encoding="utf-8")
            browser_args = [
                str(self.browser),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-sandbox",
                f"--user-data-dir={browser_profile}",
                f"--window-size={width},800",
                "--virtual-time-budget=1000",
            ]
            if reduced_motion:
                browser_args.append("--force-prefers-reduced-motion")
            browser_args.extend(("--dump-dom", fixture.as_uri()))
            result = subprocess.run(
                browser_args,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        marker = 'data-result="'
        self.assertIn(
            marker,
            result.stdout,
            msg=f"Browser output missing layout result. stderr: {result.stderr}",
        )
        encoded = result.stdout.split(marker, 1)[1].split('"', 1)[0]
        return json.loads(encoded.replace("&quot;", '"'))

    def child_tile_column_count(self, width):
        css_uri = CATALOG_CSS.resolve().as_uri()
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"><link rel="stylesheet" href="{css_uri}"></head>
<body><div class="category-child-tiles">
  <a class="category-child-tile" href="#one">Один</a>
  <a class="category-child-tile" href="#two">Два</a>
  <a class="category-child-tile" href="#three">Три</a>
</div><script>
const columns = getComputedStyle(document.querySelector('.category-child-tiles')).gridTemplateColumns;
document.body.dataset.result = JSON.stringify({{columnCount: columns.split(' ').length}});
</script></body></html>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "category-child-tiles.html"
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
                    f"--window-size={width},800",
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
        return json.loads(encoded.replace("&quot;", '"'))["columnCount"]

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_focused_parent_stays_closed_until_hover_or_mobile_toggle(self):
        state = self.render_state(focus_link=True)
        self.assertEqual(state["nestedDisplay"], "none")
        self.assertEqual(state["activeNestedHoverRules"], 0)

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_all_category_tiles_use_the_full_panel_width(self):
        state = self.render_state(extra_group_class="nested-open")
        self.assertAlmostEqual(state["groupWidth"], state["gridInnerWidth"], delta=1)
        self.assertAlmostEqual(state["regularTileWidth"], state["gridInnerWidth"], delta=1)

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_large_category_lists_use_two_columns_on_wide_screens(self):
        state = self.render_state(large_grid=True)
        self.assertEqual(state["gridColumns"], 2)

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_large_category_lists_keep_two_columns_in_narrow_panels(self):
        state = self.render_state(large_grid=True, panel_width=360)
        self.assertEqual(state["gridColumns"], 2)

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_large_category_lists_use_one_column_on_phone_viewports(self):
        state = self.render_state(width=390, large_grid=True, panel_width=360)
        self.assertEqual(state["gridColumns"], 1)

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_second_level_rows_have_uniform_readable_geometry(self):
        state = self.render_state(extra_group_class="nested-open")
        short_height, long_height = state["regularRowHeights"]
        self.assertAlmostEqual(short_height, long_height, delta=1)
        self.assertAlmostEqual(short_height, state["parentRowHeight"], delta=1)
        self.assertGreaterEqual(short_height, 44)
        self.assertGreaterEqual(state["longNameCountGap"], 8)
        self.assertTrue(state["longNameInsideRow"])
        self.assertGreaterEqual(state["toggleSize"][0], 44)
        self.assertGreaterEqual(state["toggleSize"][1], 44)

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_expanded_nested_list_is_inset_and_keeps_44px_rows(self):
        state = self.render_state(width=390, extra_group_class="nested-open")
        left_inset, right_inset = state["nestedListInsets"]
        self.assertGreaterEqual(left_inset, 10)
        self.assertGreaterEqual(right_inset, 10)
        self.assertTrue(all(height >= 44 for height in state["nestedItemHeights"]))

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_desktop_nested_list_stays_inline_in_the_category_tile(self):
        state = self.render_state(extra_group_class="nested-open")
        self.assertEqual(state["nestedPosition"], "static")

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_reduced_motion_removes_category_tile_transitions(self):
        state = self.render_state(extra_group_class="nested-open", reduced_motion=True)
        self.assertEqual(state["motionDurations"], ["0s", "0s", "0s"])

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_nested_categories_are_stacked_in_readable_rows(self):
        state = self.render_state(extra_group_class="nested-open")
        first, second, third = state["nestedItemTops"]
        self.assertLess(first, second)
        self.assertLess(second, third)

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_mobile_toggle_updates_aria_and_closes_the_other_group(self):
        state = self.render_state(width=390, toggle_clicks=1)
        self.assertEqual(state["expandedBeforeClick"], "false")
        self.assertEqual(state["expandedAfterClick"], "true")
        self.assertFalse(state["otherGroupOpen"])
        self.assertEqual(state["otherExpanded"], "false")
        first, second, third = state["nestedItemTops"]
        self.assertLess(first, second)
        self.assertLess(second, third)

    @unittest.skipUnless(browser, "Edge or Chrome is required for layout checks")
    def test_mobile_toggle_closes_without_hover_reopening_the_list(self):
        state = self.render_state(width=390, toggle_clicks=2)
        self.assertEqual(state["expandedAfterClick"], "false")
        self.assertEqual(state["nestedDisplay"], "none")
        self.assertEqual(state["activeNestedHoverRules"], 0)

    @unittest.skipUnless(browser, "Edge or Chrome is required for responsive CSS checks")
    def test_child_tiles_use_three_two_and_one_responsive_columns(self):
        self.assertEqual(self.child_tile_column_count(1280), 3)
        self.assertEqual(self.child_tile_column_count(900), 2)
        self.assertEqual(self.child_tile_column_count(390), 1)

    def test_category_child_list_has_progressive_disclosure_controls(self):
        template = CATALOG_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("category-child-tile--hidden", template)
        self.assertIn("category-child-tiles-toggle", template)
        self.assertIn("category-child-tiles--expanded", template)


if __name__ == "__main__":
    unittest.main()
