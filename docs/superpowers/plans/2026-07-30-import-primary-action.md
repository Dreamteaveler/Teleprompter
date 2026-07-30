# Import Primary Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make “导入文件” the only yellow emphasized action in the manuscript page’s global navigation while changing “新建稿件” to the secondary grey style.

**Architecture:** Keep the existing two buttons, ordering, signals, and dimensions unchanged. Swap the buttons’ `objectName` style contracts so the existing `accentButton` rule applies to import and the existing `ghostButton` rule applies to new manuscript; keep keyboard focus visible with a neutral white focus border on secondary actions so the brand yellow remains exclusive to import.

**Tech Stack:** Python 3, PyQt6 Widgets, Qt style sheets, `unittest`, Qt offscreen platform.

## Global Constraints

- Work on branch `codex/prompter-font-policy`, never directly on `master`.
- “导入文件” is the only yellow solid emphasized button in the first navigation row.
- “新建稿件” uses the grey secondary button style.
- A focused secondary button does not use the brand-yellow border; breadcrumb focus may remain yellow.
- Button order remains “新建稿件” followed by “导入文件”.
- Button click behavior and all import/new-manuscript data flows remain unchanged.
- Back up each existing code or test file before its first modification to `Backup/<filename>_yyyy-MM-dd_HHmmss.bak`.
- Keep at most the newest 30 backups for each original filename and do not stage backup files.
- Write and observe a failing test before changing production code.

---

### Task 1: Swap the Global Action Emphasis

**Files:**
- Modify: `tests/test_home_page_navigation.py`
- Modify: `app/pages/home_page.py:308-322`
- Modify: `app/styles/theme.qss:78-86`

**Interfaces:**
- Consumes: existing `HomePage._new_manuscript_button` and `HomePage._import_button`.
- Produces: `objectName() == "accentButton"` only for `_import_button`.
- Produces: `objectName() == "ghostButton"` for `_new_manuscript_button`.
- Produces: neutral white focus border for `ghostButton`, with the breadcrumb focus rule remaining brand yellow.

- [ ] **Step 1: Create incremental backups**

Run the project backup helper for:

```text
tests/test_home_page_navigation.py
app/pages/home_page.py
app/styles/theme.qss
```

Verify the new backups are inside `Backup` and remain untracked.

- [ ] **Step 2: Write the failing style-contract test**

Add this independent behavior to `HomePageNavigationTest`:

```python
def test_import_is_the_only_accented_global_action(self):
    page = self._create_page()
    global_actions = (
        page._new_manuscript_button,
        page._import_button,
    )

    accented_actions = [
        button.text()
        for button in global_actions
        if button.objectName() == "accentButton"
    ]

    self.assertEqual(accented_actions, ["导入文件"])
    self.assertEqual(
        page._new_manuscript_button.objectName(),
        "ghostButton",
    )
```

This test guards the style-selector boundary used by `theme.qss`. Reversing either style assignment must fail it.

- [ ] **Step 3: Run the focused test and verify RED**

Run the navigation test file with the existing temporary PyQt6 dependencies:

```text
python -m unittest tests/test_home_page_navigation.py -v
```

Expected failure:

```text
accented_actions is ["新建稿件"], not ["导入文件"]
```

- [ ] **Step 4: Implement the minimal style swap**

In `HomePage._init_ui`, change only:

```python
self._new_manuscript_button.setObjectName("ghostButton")
```

and:

```python
self._import_button.setObjectName("accentButton")
```

Do not reorder the widgets or reconnect their signals.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```text
python -m unittest tests/test_home_page_navigation.py -v
```

Expected: every navigation test passes.

- [ ] **Step 6: Write the failing rendered-focus test**

Add a real Qt rendering assertion:

```python
def test_focused_secondary_action_contains_no_brand_yellow(self):
    original_style = self._app.styleSheet()
    theme_path = (
        Path(__file__).parents[1]
        / "app"
        / "styles"
        / "theme.qss"
    )
    self._app.setStyleSheet(theme_path.read_text(encoding="utf-8"))
    try:
        page = self._create_page()
        page.resize(1280, 720)
        page.show()
        page._new_manuscript_button.setFocus()
        self._app.processEvents()

        gold = QColor("#DB9D16").rgb() & 0xFFFFFF

        def count_gold_pixels(button):
            image = button.grab().toImage()
            return sum(
                1
                for y in range(image.height())
                for x in range(image.width())
                if image.pixel(x, y) & 0xFFFFFF == gold
            )

        self.assertEqual(
            count_gold_pixels(page._new_manuscript_button),
            0,
        )
        self.assertGreater(
            count_gold_pixels(page._import_button),
            1000,
        )
    finally:
        self._app.setStyleSheet(original_style)
```

Import `QColor` from `PyQt6.QtGui`.

- [ ] **Step 7: Run the rendered-focus test and verify RED**

Run the navigation tests. Expected: the new test fails because the focused `ghostButton` contains an exact `#DB9D16` border.

- [ ] **Step 8: Make secondary focus neutral**

Split the combined focus selector in `theme.qss`:

```css
QPushButton#ghostButton:focus {
    color: #f2f2f2;
    border: 1px solid #f2f2f2;
}

QPushButton#breadcrumbBtn:focus {
    color: #f2f2f2;
    border: 1px solid #DB9D16;
}
```

Keep the existing white focus border on `accentButton`.

- [ ] **Step 9: Run full automated regression**

Run:

```text
python -m unittest discover -s tests -v
python -m compileall -q app tests main.py
```

Expected: 34 tests pass and compilation exits 0.

- [ ] **Step 10: Render and inspect the global navigation**

Use the existing temporary offscreen QA script to render the 1280-pixel manuscript page. Verify:

- “导入文件” is the only solid yellow button;
- “新建稿件” is grey;
- the focused “新建稿件” outline is neutral rather than yellow;
- the button order is unchanged;
- neither button is clipped;
- the second navigation row is unchanged.

- [ ] **Step 11: Commit the implementation**

Stage only:

```text
tests/test_home_page_navigation.py
app/pages/home_page.py
app/styles/theme.qss
```

Commit:

```text
git commit -m "style: 突出推荐的稿件导入操作"
```

- [ ] **Step 12: Audit the confirmed requirement**

Compare current code, the passing style-contract test, and the inspected screenshot with the revised design specification. Completion requires direct evidence that import alone is yellow and new manuscript is secondary, with position and behavior unchanged.
