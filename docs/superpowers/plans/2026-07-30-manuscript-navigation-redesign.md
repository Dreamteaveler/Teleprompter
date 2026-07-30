# Manuscript Two-Level Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the crowded manuscript-page header with a stable global navigation row and a contextual manuscript toolbar that switches in place for organize mode.

**Architecture:** `HomePage` will own a 64-pixel global header and a 52-pixel contextual toolbar backed by `QStackedLayout`. The normal toolbar contains clickable breadcrumbs, a flexible search field, folder creation, and the organize entry; the existing `BatchActionBar` becomes the alternate stacked page and gains directory/filter context without changing its signal-only responsibility.

**Tech Stack:** Python 3, PyQt6 Widgets, SQLite-backed existing application services, `unittest`, Qt offscreen platform.

## Global Constraints

- Work on branch `codex/prompter-font-policy`, never directly on `master`.
- Run `git pull --ff-only origin master` before source edits; the baseline must remain current.
- Back up every existing source/test/style file before its first modification to `Backup/<filename>_yyyy-MM-dd_HHmmss.bak`.
- Keep at most the newest 30 backups per original filename and do not touch unrelated backup files.
- Use tests first and observe the expected failure before changing production code.
- First navigation row height is exactly 64 pixels; second row height is exactly 52 pixels.
- The minimum supported window width is 960 pixels with no toolbar wrapping or horizontal scrolling.
- Preserve drag/drop import, search text, folder navigation, batch move/delete, and existing database semantics.
- Use text-only structural navigation controls; do not add emoji icons.

---

### Task 1: Context-Aware Organize Action Bar

**Files:**
- Modify: `tests/test_batch_management_widgets.py`
- Modify: `app/widgets/batch_management.py`

**Interfaces:**
- Consumes: existing `BatchActionBar.select_all_toggled`, `move_requested`, `delete_requested`, `exit_requested`.
- Produces: `BatchActionBar.set_context(path_text: str, filter_text: str = "") -> None`.
- Produces: `BatchActionBar.set_compact(compact: bool) -> None`.
- Produces: public widgets `context_label`, `filter_label`, `select_all_checkbox`, `count_label`, `move_button`, `delete_button`, `exit_button`.

- [ ] **Step 1: Create incremental backups**

Create timestamped backups of `tests/test_batch_management_widgets.py` and `app/widgets/batch_management.py`, then prune only matching backup series beyond 30 files.

- [ ] **Step 2: Write failing widget tests**

Add these behaviors to `BatchManagementWidgetsTest`:

```python
def test_action_bar_uses_organize_copy_and_context(self):
    bar = BatchActionBar()

    bar.set_context("全部稿件 › 项目", "演讲")
    bar.set_selection_state(selected_count=2, visible_count=3)

    self.assertEqual(bar.context_label.text(), "全部稿件 › 项目")
    self.assertEqual(bar.filter_label.text(), "筛选：“演讲”")
    self.assertTrue(bar.filter_label.isVisibleTo(bar))
    self.assertEqual(bar.count_label.text(), "已选 2 项")
    self.assertEqual(bar.move_button.text(), "移入文件夹")
    self.assertEqual(bar.exit_button.text(), "完成")


def test_action_bar_hides_empty_filter_and_uses_compact_margins(self):
    bar = BatchActionBar()

    bar.set_context("全部稿件")
    bar.set_compact(True)

    self.assertFalse(bar.filter_label.isVisibleTo(bar))
    self.assertEqual(bar.layout().contentsMargins().left(), 24)

    bar.set_compact(False)

    self.assertEqual(bar.layout().contentsMargins().left(), 40)
```

Update the existing count assertions from “已选择 N 篇” to “已选 N 项”.

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```text
python -m unittest tests.test_batch_management_widgets.BatchManagementWidgetsTest -v
```

Expected: the new tests fail because `set_context`, `set_compact`, `context_label`, and `filter_label` do not exist and the old copy is still present.

- [ ] **Step 4: Implement the minimal action-bar behavior**

In `BatchActionBar.__init__`, place context before selection controls:

```python
self.context_label = QLabel("全部稿件")
self.context_label.setObjectName("toolbarContext")
self.context_label.setMaximumWidth(180)
layout.addWidget(self.context_label)

self.filter_label = QLabel()
self.filter_label.setObjectName("filterHint")
self.filter_label.setMaximumWidth(140)
self.filter_label.hide()
layout.addWidget(self.filter_label)
```

Use the approved labels:

```python
self.count_label = QLabel("已选 0 项")
self.move_button = QPushButton("移入文件夹")
self.exit_button = QPushButton("完成")
```

Add:

```python
def set_context(self, path_text: str, filter_text: str = ""):
    self.context_label.setText(path_text)
    filter_text = filter_text.strip()
    self.filter_label.setText(
        f"筛选：“{filter_text}”" if filter_text else ""
    )
    self.filter_label.setVisible(bool(filter_text))

def set_compact(self, compact: bool):
    margin = 24 if compact else 40
    self.layout().setContentsMargins(margin, 8, margin, 8)
```

Change `set_selection_state` to write `f"已选 {selected_count} 项"` while preserving enabled and tri-state behavior.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the same `unittest` command. Expected: all widget tests pass with no warnings or errors.

- [ ] **Step 6: Commit Task 1**

Stage only the two Task 1 files and commit:

```text
git commit -m "refactor: 让整理操作栏承载文稿上下文"
```

---

### Task 2: Build the Two-Level Normal Navigation

**Files:**
- Create: `tests/test_home_page_navigation.py`
- Modify: `app/pages/home_page.py`
- Modify: `app/styles/theme.qss`

**Interfaces:**
- Consumes: existing `HomePage.navigate_to_editor`, `_import_file_dialog`, `_on_new_folder`, `_toggle_batch_mode`, `_update_breadcrumb`.
- Produces: `HomePage._global_header`, `_document_toolbar`, `_toolbar_stack`, `_normal_toolbar`, `_new_manuscript_button`, `_import_button`, `_new_folder_button`, `_organize_button`.
- Produces: `HomePage._current_path_text() -> str`.

- [ ] **Step 1: Create incremental backups**

Back up `app/pages/home_page.py` and `app/styles/theme.qss`, pruning only their own backup series beyond 30 files. `tests/test_home_page_navigation.py` is new and needs no backup.

- [ ] **Step 2: Write the navigation test fixture and failing normal-state test**

Create an isolated-database Qt test using the setup/teardown pattern from `tests/test_home_page_batch_mode.py`:

```python
def test_home_page_uses_two_level_navigation(self):
    page = self._create_page()

    self.assertEqual(page._global_header.height(), 64)
    self.assertEqual(page._document_toolbar.height(), 52)
    self.assertIs(
        page._toolbar_stack.currentWidget(),
        page._normal_toolbar,
    )
    self.assertEqual(page._new_manuscript_button.text(), "新建稿件")
    self.assertEqual(page._import_button.text(), "导入文件")
    self.assertEqual(page._new_folder_button.text(), "新建文件夹")
    self.assertEqual(page._organize_button.text(), "整理稿件")
    self.assertIs(page._search_input.parentWidget(), page._normal_toolbar)
    self.assertEqual(page._count_label.text(), "共 0 项")
```

Add a containment assertion that the four normal contextual controls are descendants of `_normal_toolbar`, while the two global actions are descendants of `_global_header`.

- [ ] **Step 3: Run the focused test and verify RED**

Run:

```text
python -m unittest tests.test_home_page_navigation.HomePageNavigationTest.test_home_page_uses_two_level_navigation -v
```

Expected: failure because the new navigation attributes and 64/52 split do not exist.

- [ ] **Step 4: Implement the two navigation rows**

Import `QStackedLayout`. Replace the current 72-pixel header plus standalone breadcrumb and batch bar with:

```python
self._global_header = QFrame()
self._global_header.setObjectName("globalHeader")
self._global_header.setFixedHeight(64)
header_layout = QHBoxLayout(self._global_header)
header_layout.setContentsMargins(24, 10, 24, 10)

logo = QLabel("提词器")
logo.setObjectName("appTitle")
header_layout.addWidget(logo)
header_layout.addStretch()

self._new_manuscript_button = QPushButton("新建稿件")
self._new_manuscript_button.setObjectName("accentButton")
self._new_manuscript_button.clicked.connect(
    lambda: self.navigate_to_editor.emit(None)
)
header_layout.addWidget(self._new_manuscript_button)

self._import_button = QPushButton("导入文件")
self._import_button.setObjectName("ghostButton")
self._import_button.clicked.connect(self._import_file_dialog)
header_layout.addWidget(self._import_button)
layout.addWidget(self._global_header)
```

Create the contextual stack:

```python
self._document_toolbar = QFrame()
self._document_toolbar.setObjectName("documentToolbar")
self._document_toolbar.setFixedHeight(52)
self._toolbar_stack = QStackedLayout(self._document_toolbar)
self._toolbar_stack.setContentsMargins(0, 0, 0, 0)

self._normal_toolbar = QWidget()
normal_layout = QHBoxLayout(self._normal_toolbar)
normal_layout.setContentsMargins(40, 8, 40, 8)
normal_layout.setSpacing(8)
```

Move the existing breadcrumb widget and search field into `_normal_toolbar`. Use:

```python
self._search_input.setPlaceholderText("搜索稿件…")
self._search_input.setMinimumWidth(180)
self._search_input.setMaximumWidth(360)
self._search_input.setFixedHeight(36)
```

Add text-only `_new_folder_button` and `_organize_button`, connect them to `_on_new_folder` and `_toggle_batch_mode`, add the existing `_batch_bar` as the second stack page, select `_normal_toolbar`, then add `_document_toolbar` to the page layout.

Change the content count label to `f"共 {total_items} 项"` for both root and folder views.

- [ ] **Step 5: Add navigation-specific theme rules**

Replace the single `QFrame#header` rule with:

```css
QFrame#globalHeader {
    background-color: rgba(13, 13, 13, 0.85);
    border-bottom: 1px solid #2e2e2e;
}

QLabel#appTitle {
    color: #f2f2f2;
    font-size: 18px;
    font-weight: 700;
}

QFrame#documentToolbar {
    background-color: #101010;
    border-bottom: 1px solid #2e2e2e;
}

QLabel#toolbarContext {
    color: #f2f2f2;
    font-weight: 600;
}

QLabel#filterHint {
    color: #9e9e9e;
    background-color: #1a1a1a;
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    padding: 3px 8px;
}
```

Make `QFrame#batchActionBar` transparent and borderless because the outer `documentToolbar` owns the second-row surface.

- [ ] **Step 6: Run focused navigation and existing batch tests**

Run:

```text
python -m unittest tests.test_home_page_navigation tests.test_home_page_batch_mode tests.test_batch_management_widgets -v
```

Expected: all focused UI tests pass.

- [ ] **Step 7: Commit Task 2**

Stage the new test plus `home_page.py` and `theme.qss`, then commit:

```text
git commit -m "feat: 将文稿页拆分为两级导航"
```

---

### Task 3: Switch the Second Level In Place for Organize Mode

**Files:**
- Modify: `tests/test_home_page_navigation.py`
- Modify: `app/pages/home_page.py`

**Interfaces:**
- Consumes: Task 1 `BatchActionBar.set_context` and Task 2 `_toolbar_stack`.
- Produces: `HomePage._sync_organize_toolbar_context() -> None`.
- Produces: unchanged external batch-mode behavior with stacked visual state.

- [ ] **Step 1: Back up files before their first Task 3 modification**

Create new timestamped incremental backups of both files because Task 2 has changed them since the prior backup.

- [ ] **Step 2: Write failing organize-state tests**

Add:

```python
def test_organize_mode_replaces_second_level_and_preserves_search(self):
    folder = database.create_folder("项目")
    database.create_manuscript("演讲稿", "body", folder_id=folder.id)
    page = self._create_page()
    page._on_folder_selected(folder.id)
    page._search_input.setText("演讲")

    page._enter_batch_mode()

    self.assertIs(
        page._toolbar_stack.currentWidget(),
        page._batch_bar,
    )
    self.assertEqual(page._batch_bar.context_label.text(), "全部稿件 › 项目")
    self.assertEqual(page._batch_bar.filter_label.text(), "筛选：“演讲”")
    self.assertEqual(page._search_input.text(), "演讲")

    page._exit_batch_mode()

    self.assertIs(
        page._toolbar_stack.currentWidget(),
        page._normal_toolbar,
    )
    self.assertEqual(page._search_input.text(), "演讲")


def test_nested_folder_context_uses_text_only_clickable_breadcrumbs(self):
    parent = database.create_folder("项目")
    child = database.create_folder("子文件夹", parent_id=parent.id)
    page = self._create_page()

    page._on_folder_selected(child.id)

    self.assertEqual(page._current_path_text(), "全部稿件 › 项目 › 子文件夹")
    texts = [
        button.text()
        for button in page._breadcrumb.findChildren(QPushButton)
    ]
    self.assertIn("全部稿件", texts)
    self.assertIn("项目", texts)
    self.assertIn("子文件夹", texts)
    self.assertTrue(all("📂" not in text and "📁" not in text for text in texts))
```

- [ ] **Step 3: Run the two new tests and verify RED**

Run both named tests with `python -m unittest ... -v`.

Expected: failures because stack switching, context synchronization, `_current_path_text`, and text-only breadcrumbs are not implemented.

- [ ] **Step 4: Implement context and stack synchronization**

Add:

```python
def _current_path_text(self) -> str:
    names = ["全部稿件", *(folder.name for folder in self._folder_path)]
    return " › ".join(names)

def _sync_organize_toolbar_context(self):
    self._batch_bar.set_context(
        self._current_path_text(),
        self._search_input.text(),
    )
```

In `_enter_batch_mode`, synchronize context and select `_batch_bar` in `_toolbar_stack`. In `_exit_batch_mode`, select `_normal_toolbar`. Remove all references to `_batch_manage_button` and its old text changes.

Update `_update_breadcrumb` to render “全部稿件” and folder names without emoji. Preserve each button’s existing click target, current-node color, hover behavior, folder submenu, and root navigation.

- [ ] **Step 5: Run focused UI tests and verify GREEN**

Run:

```text
python -m unittest tests.test_home_page_navigation tests.test_home_page_batch_mode tests.test_batch_management_widgets -v
```

Expected: all focused tests pass and the existing search-preservation tests remain green.

- [ ] **Step 6: Commit Task 3**

Stage only the two Task 3 files and commit:

```text
git commit -m "feat: 在第二级导航中切换整理模式"
```

---

### Task 4: Responsive Layout, Visual QA, and Full Regression

**Files:**
- Modify: `tests/test_home_page_navigation.py`
- Modify: `app/pages/home_page.py`
- Modify: `app/styles/theme.qss` only if visual QA exposes a layout defect.

**Interfaces:**
- Consumes: Task 2 toolbar layouts and Task 1 `BatchActionBar.set_compact`.
- Produces: `HomePage._update_toolbar_responsiveness(width: int) -> None`.

- [ ] **Step 1: Back up files before Task 4 modifications**

Back up each existing file that Task 4 will change and prune only its matching backup series beyond 30.

- [ ] **Step 2: Write failing responsive test**

Add:

```python
def test_toolbar_uses_compact_margins_at_minimum_window_width(self):
    page = self._create_page()
    page.resize(960, 540)
    self._app.processEvents()

    normal_margins = page._normal_toolbar.layout().contentsMargins()
    batch_margins = page._batch_bar.layout().contentsMargins()

    self.assertEqual(normal_margins.left(), 24)
    self.assertEqual(normal_margins.right(), 24)
    self.assertEqual(batch_margins.left(), 24)
    self.assertEqual(batch_margins.right(), 24)
    self.assertGreaterEqual(page._search_input.minimumWidth(), 180)
```

- [ ] **Step 3: Run the responsive test and verify RED**

Expected: it fails because the layouts still use 40-pixel margins at 960 pixels.

- [ ] **Step 4: Implement responsive margins**

Add:

```python
def _update_toolbar_responsiveness(self, width: int):
    compact = width < 1100
    margin = 24 if compact else 40
    self._normal_toolbar.layout().setContentsMargins(
        margin, 8, margin, 8
    )
    self._batch_bar.set_compact(compact)
```

Call it after toolbar construction and from `resizeEvent`. Keep the search minimum width at 180 pixels and maximum at 360 pixels. Do not introduce a horizontal scrollbar.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run all navigation, batch-mode, and batch-widget tests. Expected: all pass.

- [ ] **Step 6: Run full automated regression**

Run:

```text
python -m unittest discover -s tests -v
python -m compileall -q app tests main.py
```

Expected: every test passes, compile check exits 0, and output contains no Qt errors.

- [ ] **Step 7: Render offscreen screenshots at 1280 and 960 pixels**

Create a temporary non-repository QA script that:

- sets `QT_QPA_PLATFORM=offscreen`;
- creates sample root and nested folders plus manuscripts in a temporary database;
- renders normal mode at 1280×720;
- renders normal mode at 960×540;
- renders organize mode with an active search;
- saves PNG files under `C:\tmp`.

Inspect each PNG and verify:

- exactly two top rows are visible;
- first row contains only title, new manuscript, and import;
- second row contains path, search, new folder, and organize;
- organize mode replaces the second row instead of adding a third;
- no button is clipped at 960 pixels;
- there is no duplicate “全部稿件” content heading;
- spacing, button hierarchy, focus outline, and dark-theme contrast remain coherent.

- [ ] **Step 8: Commit Task 4**

Stage only files changed by Task 4 and commit:

```text
git commit -m "test: 验证文稿导航的窄窗口布局"
```

- [ ] **Step 9: Final requirement audit**

Re-read `docs/superpowers/specs/2026-07-30-manuscript-navigation-redesign-design.md` and map every goal, state transition, width rule, visual rule, boundary, and test requirement to current code, passing tests, or inspected screenshots. Do not declare completion while any item lacks direct evidence.
