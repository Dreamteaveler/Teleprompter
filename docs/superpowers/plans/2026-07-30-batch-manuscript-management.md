# 讲稿批量管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在讲稿管理页增加仅限当前可见讲稿的批量选择模式，并支持原子化批量移动到文件夹、现场新建目标文件夹和永久删除。

**Architecture:** 保留现有卡片布局，由 `HomePage` 管理选择状态，`ManuscriptCard` 只负责单卡交互；新增独立的 `BatchActionBar` 和 `FolderPickerDialog`，避免继续扩大页面职责。数据库层提供去重、跳过无变化行并在单次事务中完成的批量移动和删除接口。

**Tech Stack:** Python 3.12、PyQt6、SQLite、`unittest`、Qt 离屏测试。

## Global Constraints

- 不新增数据库表或字段；整理只更新 `manuscripts.parent_folder_id`。
- 多选仅限当前界面可见讲稿；切换目录、面包屑或搜索条件必须退出批量模式并清空选择。
- 文件夹不能被选中；普通模式的播放、编辑和单篇删除行为保持不变。
- 批量移动和删除必须各自在单个 SQLite 事务中完成，失败时整批回滚。
- 目标选择器必须支持根目录、任意层级文件夹，以及在当前选中目标下现场新建文件夹。
- 已在目标文件夹的讲稿不得更新 `updated_at`，也不得计入实际移动数量。
- 修改现有重要文件前，在 `Backup` 创建 `文件名_yyyy-MM-dd_HHmmss.bak` 增量备份；同一文件最多保留最近 30 份。
- 保留现有 6 个 `2026-07-30_110744` 未跟踪备份，不暂存、不修改。
- 不增加第三方依赖。

---

### Task 1: 原子化批量数据库操作

**Files:**
- Create: `tests/test_batch_manuscript_database.py`
- Modify: `app/database.py:9-14`
- Modify: `app/database.py:264-268`
- Modify: `app/database.py:335-352`
- Backup: `Backup/database.py_<timestamp>.bak`

**Interfaces:**
- Consumes: 现有 `get_connection()`、`now_iso()` 和 SQLite 外键约束。
- Produces: `move_manuscripts(manuscript_ids: Iterable[int], target_folder_id: int | None) -> int`。
- Produces: `delete_manuscripts(manuscript_ids: Iterable[int]) -> int`。
- Preserves: `move_manuscripts_batch(manuscript_ids: list[int], target_folder_id: int | None) -> int` 兼容包装。

- [ ] **Step 1: 为数据库文件创建增量备份**

使用 Python `shutil.copy2` 将 `app/database.py` 复制为：

```text
Backup/database.py_yyyy-MM-dd_HHmmss.bak
```

按修改时间保留最新 30 个 `database.py_*.bak`。

- [ ] **Step 2: 写批量移动和删除的失败测试**

创建隔离临时数据库测试，复用与 `tests/test_folder_deletion.py` 相同的路径切换和连接清理方式。核心测试应包含：

```python
def test_move_manuscripts_moves_only_changed_rows(self):
    source = database.create_folder("来源")
    target = database.create_folder("目标")
    first = database.create_manuscript("一", "one", folder_id=source.id)
    second = database.create_manuscript("二", "two", folder_id=target.id)
    second_updated_at = second.updated_at

    changed = database.move_manuscripts(
        [first.id, second.id, first.id],
        target.id,
    )

    self.assertEqual(changed, 1)
    self.assertEqual(database.get_manuscript(first.id).parent_folder_id, target.id)
    unchanged = database.get_manuscript(second.id)
    self.assertEqual(unchanged.parent_folder_id, target.id)
    self.assertEqual(unchanged.updated_at, second_updated_at)


def test_move_manuscripts_to_root(self):
    folder = database.create_folder("来源")
    manuscript = database.create_manuscript("稿件", "body", folder_id=folder.id)

    changed = database.move_manuscripts([manuscript.id], None)

    self.assertEqual(changed, 1)
    self.assertIsNone(database.get_manuscript(manuscript.id).parent_folder_id)


def test_move_manuscripts_rolls_back_for_invalid_target(self):
    source = database.create_folder("来源")
    first = database.create_manuscript("一", "one", folder_id=source.id)
    second = database.create_manuscript("二", "two", folder_id=source.id)

    with self.assertRaises(sqlite3.IntegrityError):
        database.move_manuscripts([first.id, second.id], 999_999)

    self.assertEqual(database.get_manuscript(first.id).parent_folder_id, source.id)
    self.assertEqual(database.get_manuscript(second.id).parent_folder_id, source.id)


def test_delete_manuscripts_deletes_existing_selected_rows_only(self):
    first = database.create_manuscript("一", "one")
    second = database.create_manuscript("二", "two")
    survivor = database.create_manuscript("保留", "keep")

    deleted = database.delete_manuscripts([first.id, second.id, first.id, 999_999])

    self.assertEqual(deleted, 2)
    self.assertIsNone(database.get_manuscript(first.id))
    self.assertIsNone(database.get_manuscript(second.id))
    self.assertIsNotNone(database.get_manuscript(survivor.id))


def test_empty_batch_does_not_modify_database(self):
    manuscript = database.create_manuscript("保留", "keep")

    self.assertEqual(database.move_manuscripts([], None), 0)
    self.assertEqual(database.delete_manuscripts([]), 0)
    self.assertIsNotNone(database.get_manuscript(manuscript.id))
```

- [ ] **Step 3: 运行测试并确认因接口不存在而失败**

Run:

```text
python -m unittest discover -s tests -p test_batch_manuscript_database.py -v
```

Expected: FAIL，错误包含 `module 'app.database' has no attribute 'move_manuscripts'` 或 `delete_manuscripts`。

- [ ] **Step 4: 实现 ID 规范化和批量数据库接口**

在 `app/database.py` 引入 `Iterable`，实现：

```python
from collections.abc import Iterable


def _unique_ids(values: Iterable[int]) -> tuple[int, ...]:
    return tuple(dict.fromkeys(int(value) for value in values))


def delete_manuscripts(manuscript_ids: Iterable[int]) -> int:
    ids = _unique_ids(manuscript_ids)
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    with get_connection() as conn:
        cursor = conn.execute(
            f"DELETE FROM manuscripts WHERE id IN ({placeholders})",
            ids,
        )
        conn.commit()
        return cursor.rowcount


def move_manuscripts(
    manuscript_ids: Iterable[int],
    target_folder_id: int | None,
) -> int:
    ids = _unique_ids(manuscript_ids)
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    now = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            f"""
            UPDATE manuscripts
            SET parent_folder_id = ?, updated_at = ?
            WHERE id IN ({placeholders})
              AND parent_folder_id IS NOT ?
            """,
            (target_folder_id, now, *ids, target_folder_id),
        )
        conn.commit()
        return cursor.rowcount


def move_manuscripts_batch(
    manuscript_ids: list[int],
    target_folder_id: int | None,
) -> int:
    return move_manuscripts(manuscript_ids, target_folder_id)
```

保留 `delete_manuscript()`；它可以继续使用单行 SQL，也可以调用 `delete_manuscripts([manuscript_id]) > 0`，但外部行为不得改变。

- [ ] **Step 5: 运行数据库测试并确认通过**

Run:

```text
python -m unittest discover -s tests -p "test_*database.py" -v
python -m unittest discover -s tests -p test_folder_deletion.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 6: 提交数据库任务**

```text
git add app/database.py tests/test_batch_manuscript_database.py Backup/database.py_<timestamp>.bak
git commit -m "feat: 添加讲稿批量数据库操作"
```

---

### Task 2: 批量操作栏与文件夹选择窗口

**Files:**
- Create: `app/widgets/__init__.py`
- Create: `app/widgets/batch_management.py`
- Create: `tests/test_batch_management_widgets.py`
- Modify: `app/styles/theme.qss:193-220`
- Modify: `app/styles/theme.qss:316-350`
- Backup: `Backup/theme.qss_<timestamp>.bak`

**Interfaces:**
- Consumes: `get_all_folders()`、`create_folder()` 和 `Folder`。
- Produces: `BatchActionBar.select_all_toggled(bool)`。
- Produces: `BatchActionBar.move_requested()`、`delete_requested()`、`exit_requested()`。
- Produces: `BatchActionBar.set_selection_state(selected_count: int, visible_count: int) -> None`。
- Produces: `FolderPickerDialog.selected_folder_id() -> int | None`。

- [ ] **Step 1: 为主题文件创建增量备份**

复制 `app/styles/theme.qss` 为 `Backup/theme.qss_yyyy-MM-dd_HHmmss.bak`，并保留最近 30 份。

- [ ] **Step 2: 写组件失败测试**

测试进程必须在导入 PyQt6 前设置：

```python
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

创建一次 `QApplication`，并使用临时数据库测试真实文件夹创建行为：

```python
def test_action_bar_reflects_selection_state(self):
    bar = BatchActionBar()

    bar.set_selection_state(selected_count=0, visible_count=3)
    self.assertFalse(bar.move_button.isEnabled())
    self.assertFalse(bar.delete_button.isEnabled())
    self.assertEqual(bar.count_label.text(), "已选择 0 篇")

    bar.set_selection_state(selected_count=3, visible_count=3)
    self.assertTrue(bar.move_button.isEnabled())
    self.assertTrue(bar.delete_button.isEnabled())
    self.assertEqual(
        bar.select_all_checkbox.checkState(),
        Qt.CheckState.Checked,
    )


def test_folder_picker_builds_nested_tree_and_supports_root(self):
    parent = database.create_folder("父文件夹")
    child = database.create_folder("子文件夹", parent_id=parent.id)
    dialog = FolderPickerDialog()

    self.assertTrue(dialog.select_folder(parent.id))
    self.assertEqual(dialog.selected_folder_id(), parent.id)
    self.assertTrue(dialog.select_folder(child.id))
    self.assertEqual(dialog.selected_folder_id(), child.id)
    self.assertTrue(dialog.select_folder(None))
    self.assertIsNone(dialog.selected_folder_id())


def test_folder_picker_creates_and_selects_child_folder(self):
    parent = database.create_folder("父文件夹")
    dialog = FolderPickerDialog()
    dialog.select_folder(parent.id)

    created = dialog.create_folder_under_selection("  新分类  ")

    self.assertEqual(created.name, "新分类")
    self.assertEqual(created.parent_folder_id, parent.id)
    self.assertEqual(dialog.selected_folder_id(), created.id)
```

- [ ] **Step 3: 运行组件测试并确认导入失败**

Run:

```text
python -m unittest discover -s tests -p test_batch_management_widgets.py -v
```

Expected: FAIL，错误包含 `No module named 'app.widgets'`。

- [ ] **Step 4: 实现 `BatchActionBar`**

在 `app/widgets/batch_management.py` 中创建 `QFrame` 子类：

```python
class BatchActionBar(QFrame):
    select_all_toggled = pyqtSignal(bool)
    move_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def set_selection_state(self, selected_count: int, visible_count: int):
        self.count_label.setText(f"已选择 {selected_count} 篇")
        has_selection = selected_count > 0
        self.move_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.select_all_checkbox.setEnabled(visible_count > 0)

        if selected_count == 0:
            state = Qt.CheckState.Unchecked
        elif selected_count == visible_count:
            state = Qt.CheckState.Checked
        else:
            state = Qt.CheckState.PartiallyChecked

        blocked = self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setCheckState(state)
        self.select_all_checkbox.blockSignals(blocked)
```

复选框状态变化时，仅在最终状态为 `Checked` 时发出 `True`，其他状态发出 `False`。按钮使用可公开测试的属性名：`move_button`、`delete_button`、`exit_button`、`count_label`、`select_all_checkbox`。

- [ ] **Step 5: 实现 `FolderPickerDialog`**

使用 `QTreeWidget` 和 `QDialogButtonBox`。根节点数据使用内部哨兵值，公开接口把它转换为 `None`：

```python
ROOT_FOLDER = -1


def selected_folder_id(self) -> int | None:
    item = self.tree.currentItem()
    if item is None:
        return None
    folder_id = item.data(0, Qt.ItemDataRole.UserRole)
    return None if folder_id == ROOT_FOLDER else int(folder_id)


def create_folder_under_selection(self, name: str) -> Folder:
    normalized = name.strip()
    if not normalized:
        raise ValueError("文件夹名称不能为空")
    parent_id = self.selected_folder_id()
    folder = create_folder(normalized, parent_id=parent_id)
    self.reload_tree(select_folder_id=folder.id)
    return folder
```

`select_folder(folder_id)` 和 `reload_tree(select_folder_id=None)` 是生产逻辑：前者供初始化及新建后的自动选择使用，后者构造完整层级。界面“新建文件夹”按钮通过 `QInputDialog.getText` 获取名称，捕获异常后用 `QMessageBox.warning` 提示并保持窗口打开。

- [ ] **Step 6: 增加组件主题样式**

在 `theme.qss` 增加：

```css
QFrame#batchActionBar {
    background-color: #141414;
    border-top: 1px solid #2e2e2e;
    border-bottom: 1px solid #2e2e2e;
}

QPushButton#dangerButton {
    color: #ef4444;
    border-color: rgba(239, 68, 68, 0.45);
}

QPushButton#dangerButton:hover {
    color: #ffffff;
    background-color: #b91c1c;
    border-color: #ef4444;
}

QTreeWidget#folderTree {
    background-color: #141414;
    color: #f2f2f2;
    border: 1px solid #2e2e2e;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}

QTreeWidget#folderTree::item {
    min-height: 30px;
    padding: 2px 6px;
}

QTreeWidget#folderTree::item:selected {
    background-color: rgba(219, 157, 22, 0.2);
    color: #DB9D16;
}
```

- [ ] **Step 7: 运行组件和编译测试**

Run:

```text
python -m unittest discover -s tests -p test_batch_management_widgets.py -v
python -m compileall -q app/widgets tests/test_batch_management_widgets.py
```

Expected: 全部 PASS，编译退出码为 `0`。

- [ ] **Step 8: 提交组件任务**

```text
git add app/widgets app/styles/theme.qss tests/test_batch_management_widgets.py Backup/theme.qss_<timestamp>.bak
git commit -m "feat: 添加批量操作栏和文件夹选择器"
```

---

### Task 3: 讲稿卡片与首页批量流程

**Files:**
- Create: `tests/test_home_page_batch_mode.py`
- Modify: `app/pages/home_page.py:9-25`
- Modify: `app/pages/home_page.py:35-123`
- Modify: `app/pages/home_page.py:206-304`
- Modify: `app/pages/home_page.py:305-333`
- Modify: `app/pages/home_page.py:515-638`
- Backup: `Backup/home_page.py_<timestamp>.bak`

**Interfaces:**
- Consumes: `BatchActionBar`、`FolderPickerDialog`、`move_manuscripts()`、`delete_manuscripts()`。
- Produces: `ManuscriptCard.selection_toggled(int, bool)`。
- Produces: `HomePage._batch_mode: bool` 和 `HomePage._selected_manuscript_ids: set[int]`。
- Preserves: `HomePage.navigate_to_prompter`、`navigate_to_editor` 及现有导入、文件夹导航流程。

- [ ] **Step 1: 为首页文件创建增量备份**

复制 `app/pages/home_page.py` 为 `Backup/home_page.py_yyyy-MM-dd_HHmmss.bak`，保留最近 30 份。

- [ ] **Step 2: 写讲稿卡片和首页批量状态失败测试**

使用离屏 `QApplication` 和临时数据库，创建两个根目录讲稿、一个子文件夹及其中稿件。核心断言：

```python
def test_card_checkbox_toggles_selection_without_playing(self):
    manuscript = database.create_manuscript("稿件", "body")
    card = ManuscriptCard(manuscript, batch_mode=True, selected=False)
    selected = []
    played = []
    card.selection_toggled.connect(lambda mid, value: selected.append((mid, value)))
    card.play_clicked.connect(played.append)

    card.selection_checkbox.click()

    self.assertEqual(selected, [(manuscript.id, True)])
    self.assertEqual(played, [])
    self.assertTrue(card.is_selected())


def test_home_page_select_all_uses_visible_manuscripts_only(self):
    first = database.create_manuscript("可见一", "one")
    second = database.create_manuscript("可见二", "two")
    folder = database.create_folder("文件夹")
    database.create_manuscript("隐藏", "hidden", folder_id=folder.id)
    page = HomePage()

    page._enter_batch_mode()
    page._select_all_visible(True)

    self.assertEqual(page._selected_manuscript_ids, {first.id, second.id})
    self.assertNotIn(folder.id, page._selected_manuscript_ids)


def test_search_change_exits_batch_mode_and_clears_selection(self):
    manuscript = database.create_manuscript("测试稿件", "body")
    page = HomePage()
    page._enter_batch_mode()
    page._toggle_manuscript_selection(manuscript.id, True)

    page._search_input.setText("测试")

    self.assertFalse(page._batch_mode)
    self.assertEqual(page._selected_manuscript_ids, set())
```

另加目录切换退出批量模式和批量操作栏无选择时禁用的断言。

- [ ] **Step 3: 运行首页测试并确认构造参数或方法不存在**

Run:

```text
python -m unittest discover -s tests -p test_home_page_batch_mode.py -v
```

Expected: FAIL，错误包含 `unexpected keyword argument 'batch_mode'` 或缺少 `_enter_batch_mode`。

- [ ] **Step 4: 扩展 `ManuscriptCard`**

构造函数改为：

```python
def __init__(
    self,
    manuscript: Manuscript,
    batch_mode: bool = False,
    selected: bool = False,
    parent=None,
):
```

新增：

```python
selection_toggled = pyqtSignal(int, bool)


def is_selected(self) -> bool:
    return self._selected


def set_selected(self, selected: bool):
    self._selected = selected
    blocked = self.selection_checkbox.blockSignals(True)
    self.selection_checkbox.setChecked(selected)
    self.selection_checkbox.blockSignals(blocked)
    self._apply_card_style()
```

选择复选框仅在批量模式显示。批量模式中，卡片左键点击执行 `selection_checkbox.toggle()`；普通模式仍发出 `play_clicked`。把当前 `enterEvent`/`leaveEvent` 的固定样式改成 `_apply_card_style(hovered: bool = False)`，优先显示选中金色边框，避免鼠标离开后丢失选中样式。

- [ ] **Step 5: 在 `HomePage` 初始化批量状态和操作栏**

在 `_init_ui()` 前初始化：

```python
self._batch_mode = False
self._selected_manuscript_ids: set[int] = set()
```

顶部增加 `_batch_manage_button`。面包屑下增加隐藏的 `BatchActionBar` 并连接：

```python
self._batch_bar.select_all_toggled.connect(self._select_all_visible)
self._batch_bar.move_requested.connect(self._move_selected_manuscripts)
self._batch_bar.delete_requested.connect(self._delete_selected_manuscripts)
self._batch_bar.exit_requested.connect(self._exit_batch_mode)
```

增加 `QShortcut(QKeySequence(Qt.Key.Key_Escape), self)`，上下文设置为 `WidgetWithChildrenShortcut`，触发时仅在批量模式退出。

- [ ] **Step 6: 实现选择状态方法**

实现：

```python
def _enter_batch_mode(self):
    if self._batch_mode:
        return
    self._batch_mode = True
    self._selected_manuscript_ids.clear()
    self._batch_bar.show()
    self._batch_manage_button.setText("退出批量管理")
    self._render_cards()


def _exit_batch_mode(self, render: bool = True):
    was_active = self._batch_mode or bool(self._selected_manuscript_ids)
    self._batch_mode = False
    self._selected_manuscript_ids.clear()
    self._batch_bar.hide()
    self._batch_manage_button.setText("批量管理")
    if render and was_active:
        self._render_cards()


def _toggle_manuscript_selection(self, manuscript_id: int, selected: bool):
    visible_ids = {item.id for item in self._manuscripts}
    if manuscript_id not in visible_ids:
        return
    if selected:
        self._selected_manuscript_ids.add(manuscript_id)
    else:
        self._selected_manuscript_ids.discard(manuscript_id)
    self._update_batch_bar()


def _select_all_visible(self, selected: bool):
    visible_ids = {item.id for item in self._manuscripts}
    self._selected_manuscript_ids = visible_ids if selected else set()
    self._render_cards()
```

`_render_cards()` 构造 `ManuscriptCard` 时传入批量状态和选中状态，并连接 `selection_toggled`。每次渲染前将选择集合与当前可见 ID 取交集。

- [ ] **Step 7: 在导航和搜索边界清空批量状态**

在 `_on_folder_selected()`、`_on_root_selected()`、`_on_breadcrumb_click()` 和非程序性搜索条件变化时先调用：

```python
self._exit_batch_mode(render=False)
```

为避免 `_search_input.clear()` 重复渲染，允许 `_on_search()` 统一完成最终列表刷新。目录变化后必须确保 `_batch_mode is False` 且选择集合为空。

- [ ] **Step 8: 实现批量移动流程**

```python
def _move_selected_manuscripts(self):
    manuscript_ids = tuple(self._selected_manuscript_ids)
    if not manuscript_ids:
        return
    dialog = FolderPickerDialog(self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    try:
        moved = move_manuscripts(
            manuscript_ids,
            dialog.selected_folder_id(),
        )
    except Exception as error:
        QMessageBox.warning(self, "移动失败", f"无法移动所选稿件：\n{error}")
        return
    self._exit_batch_mode(render=False)
    self._refresh()
    QMessageBox.information(self, "移动完成", f"已移动 {moved} 篇讲稿。")
```

取消对话框和异常分支不得清空当前选择。

- [ ] **Step 9: 实现批量删除流程**

从当前 `_manuscripts` 按选中 ID 获取标题，最多列前 5 个：

```python
def _batch_delete_message(self, selected: list[Manuscript]) -> str:
    titles = [item.title or "未命名稿件" for item in selected]
    preview = "\n".join(f"• {title}" for title in titles[:5])
    remainder = len(titles) - 5
    if remainder > 0:
        preview += f"\n• 另有 {remainder} 篇"
    return (
        f"确定要永久删除选中的 {len(titles)} 篇讲稿吗？\n\n"
        f"{preview}\n\n此操作不可撤销。"
    )
```

用户确认后调用 `delete_manuscripts()`；成功时退出批量模式、刷新并提示实际删除数量；取消或异常时保留选择。

- [ ] **Step 10: 运行首页、组件和数据库测试**

Run:

```text
python -m unittest discover -s tests -p test_home_page_batch_mode.py -v
python -m unittest discover -s tests -p test_batch_management_widgets.py -v
python -m unittest discover -s tests -p test_batch_manuscript_database.py -v
```

Expected: 全部 PASS。

- [ ] **Step 11: 提交首页集成任务**

```text
git add app/pages/home_page.py tests/test_home_page_batch_mode.py Backup/home_page.py_<timestamp>.bak
git commit -m "feat: 在讲稿页添加批量管理模式"
```

---

### Task 4: 文档、回归验证与交付

**Files:**
- Modify: `README.md:5-9`
- Backup: `Backup/README.md_<timestamp>.bak`

**Interfaces:**
- Consumes: 前三项任务完成的用户可见功能。
- Produces: 与当前功能一致的 README 说明和完整验证证据。

- [ ] **Step 1: 备份并更新 README**

创建 `Backup/README.md_yyyy-MM-dd_HHmmss.bak`，然后把稿件管理功能更新为：

```markdown
- 稿件管理：创建、搜索、导入 Word/TXT/Markdown、文件夹整理、批量移动与批量删除
```

- [ ] **Step 2: 运行完整测试套件**

使用安装了开发依赖的项目 Python：

```text
python -m unittest discover -s tests -v
```

Expected: 所有数据库、界面、字体和文件夹测试 PASS。

- [ ] **Step 3: 运行编译和差异检查**

```text
python -m compileall -q app tests
git diff --check
git status --short
```

Expected:

- 编译退出码 `0`；
- `git diff --check` 退出码 `0`；
- 状态中只包含本任务预期修改，以及明确保留的 6 个 `2026-07-30_110744` 未跟踪备份。

- [ ] **Step 4: 进行需求逐项审查**

逐项确认：

- “批量管理”入口存在；
- 只有讲稿出现多选框；
- 卡片点击在批量模式切换选择、普通模式播放；
- 全选只覆盖当前可见讲稿；
- 搜索和目录变化退出批量模式；
- 目标窗口支持根目录、嵌套文件夹和现场新建；
- 批量移动跳过原位置并原子提交；
- 删除确认展示数量、标题和不可撤销提示；
- 取消和失败保留选择；
- 成功后刷新并显示实际数量。

- [ ] **Step 5: 提交文档和最终调整**

```text
git add README.md Backup/README.md_<timestamp>.bak
git commit -m "docs: 更新讲稿批量管理说明"
```

- [ ] **Step 6: 确认最终提交态**

```text
git log -5 --oneline --decorate
git status --short
```

Expected: 功能提交均位于当前分支；除保留的 6 个用户备份外没有未提交修改。
