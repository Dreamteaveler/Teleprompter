# Prevent Transient Qt Windows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop transient native windows while the app creates the teleprompter page or rebuilds manuscript cards.

**Architecture:** Qt turns a QWidget without a parent into a top-level window. Construct dynamic widgets with their final owners from the start, and use a Qt event filter to detect unwanted ParentAboutToChange events.

**Tech Stack:** Python 3.12, PyQt6, unittest, SQLite test fixtures.

## Global Constraints

- Preserve manuscript, folder, import, save, and navigation behavior.
- Do not alter user data or the database schema.
- Back up every existing production source file in Backup immediately before editing it; retain at most 30 backups per source file.
- Keep the change limited to widget parent ownership; do not add timing delays or hide valid dialogs.

---

### Task 1: Add a Qt lifecycle regression test

**Files:**
- Create: `tests/test_window_parenting.py`
- Test: `tests/test_window_parenting.py`

**Interfaces:**
- Consumes: `HomePage.refresh()`, `MainWindow._ensure_prompter()`, and `QEvent.Type.ParentAboutToChange`.
- Produces: Regression coverage that fails if a dynamic content widget is initially a top-level window.

- [ ] **Step 1: Write the failing test**

```python
def test_refresh_never_reparents_dynamic_widgets_from_top_level(self):
    page = self._create_page_with_a_manuscript_and_folder()
    self.assertEqual(self._record_top_level_reparents(page.refresh), [])

def test_ensure_prompter_constructs_the_page_as_a_stack_child(self):
    window = self._create_main_window_with_a_lightweight_prompter_stub()
    self.assertEqual(self._record_top_level_reparents(window._ensure_prompter), [])
```

- [ ] **Step 2: Run the test and verify RED**

Run: `python -m unittest tests.test_window_parenting -v`

Expected: FAIL because current dynamic widgets are constructed with no parent before their visible layout reparents them.

- [ ] **Step 3: Implement the minimal parent-ownership fix**

```python
# app/pages/main_window.py
self._prompter = PrompterPage(self._stack)

# app/pages/home_page.py
self._cards_widget = QWidget(self._scroll_content)
empty = QWidget(self._cards_widget)
card = FolderCard(item, self._cards_widget)
card = ManuscriptCard(item, self._cards_widget)
```

- [ ] **Step 4: Run the test and verify GREEN**

Run: `python -m unittest tests.test_window_parenting -v`

Expected: PASS with no reparenting events for dynamic content widgets.

- [ ] **Step 5: Commit**

Run: `git add app/pages/home_page.py app/pages/main_window.py tests/test_window_parenting.py docs/superpowers/plans/2026-07-30-prevent-transient-qt-windows.md`

Run: `git commit -m "fix: prevent transient Qt windows during page rebuilds"`

### Task 2: Verify affected user flows

**Files:**
- Modify: `app/pages/home_page.py:793-895`
- Modify: `app/pages/main_window.py:65-78`
- Test: `tests/test_window_parenting.py`

**Interfaces:**
- Consumes: Existing document navigation, save callbacks, and deletion refresh paths.
- Produces: No unparented dynamic widgets during first teleprompter creation or manuscript-card redraw.

- [ ] **Step 1: Run focused coverage**

Run: `python -m unittest tests.test_window_parenting tests.test_home_page_navigation tests.test_home_page_batch_mode -v`

Expected: PASS.

- [ ] **Step 2: Run all tests**

Run: `python -m unittest discover -s tests -v`

Expected: PASS.

- [ ] **Step 3: Smoke-test the application**

Launch with existing data, enter and leave the teleprompter, import and save a disposable manuscript in an isolated test database, and refresh after deletion.

Expected: No transient window; normal explicit dialogs still work.

- [ ] **Step 4: Commit the verified result**

Run: `git status --short`

Run: `git add app/pages/home_page.py app/pages/main_window.py tests/test_window_parenting.py docs/superpowers/plans/2026-07-30-prevent-transient-qt-windows.md`

Run: `git commit -m "fix: prevent transient Qt windows during page rebuilds"`

