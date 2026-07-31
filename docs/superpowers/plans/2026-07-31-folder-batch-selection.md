# 整理模式文件夹批量选择 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 整理模式下文件夹卡片可选中，并整体参与批量移动/删除。

**Architecture:** 数据库层新增文件夹批量移动/删除/子树查询函数；界面层扩展 FolderCard 支持批量选择，HomePage 维护文件夹选择集合并联通全选/计数/移动/删除；FolderPickerDialog 禁用被选文件夹子树。

**Tech Stack:** Python 3.12, PyQt6, SQLite（单文件数据库）。

## Global Constraints

- 所有数据库批量函数接受任意可迭代 ID、去重、空集合返回 0、单事务、返回实际变更数。
- 文件夹不能移入自身或子孙：数据库层抛 `ValueError`，UI 层禁用目标节点。
- 删除文件夹时其子树内稿件一并永久删除。
- TDD：每个任务先写失败测试，确认失败后实现，确认通过后提交。
- 界面测试使用离屏 Qt（`QT_QPA_PLATFORM=offscreen`）。
- 遵守用户规则：修改前备份到 `Backup/`、git fetch、分文件提交。

---

### Task 1: 数据库层 get_folder_subtree_ids

**Files:**
- Modify: `app/database.py`（在 Folder CRUD 区新增函数）
- Test: `tests/test_folder_batch_database.py`（新建）

**Interfaces:**
- Produces: `database.get_folder_subtree_ids(folder_ids: Iterable[int]) -> set[int]`

- [ ] **Step 1: 写失败测试**

```python
def test_get_folder_subtree_ids_includes_nested_descendants(self):
    parent = database.create_folder("父")
    child = database.create_folder("子", parent_id=parent.id)
    grandchild = database.create_folder("孙", parent_id=child.id)
    other = database.create_folder("无关")

    subtree = database.get_folder_subtree_ids([parent.id])

    self.assertEqual(subtree, {parent.id, child.id, grandchild.id})
    self.assertNotIn(other.id, subtree)
```

- [ ] **Step 2: 运行确认失败**（`AttributeError: get_folder_subtree_ids`）
- [ ] **Step 3: 实现**：递归遍历 `folders.parent_folder_id`，BFS/DFS 收集子孙 ID。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: 数据库层文件夹子树查询`

### Task 2: 数据库层 move_folders

**Files:**
- Modify: `app/database.py`
- Test: `tests/test_folder_batch_database.py`

**Interfaces:**
- Consumes: `get_folder_subtree_ids`
- Produces: `database.move_folders(folder_ids: Iterable[int], target_folder_id: int | None) -> int`

- [ ] **Step 1: 写失败测试**（三个用例：移动/已在目标不计/拒绝移入子孙）

```python
def test_move_folders_moves_to_target_and_root(self):
    source = database.create_folder("来源")
    target = database.create_folder("目标")
    other = database.create_folder("其他")

    changed = database.move_folders([source.id, other.id, source.id], target.id)

    self.assertEqual(changed, 2)
    self.assertEqual(database.get_folder(source.id).parent_folder_id, target.id)
    self.assertEqual(database.get_folder(other.id).parent_folder_id, target.id)

    root_changed = database.move_folders([source.id], None)
    self.assertEqual(root_changed, 1)
    self.assertIsNone(database.get_folder(source.id).parent_folder_id)

def test_move_folders_skips_folders_already_at_target(self):
    target = database.create_folder("目标")
    child = database.create_folder("子", parent_id=target.id)
    before = child.updated_at

    changed = database.move_folders([child.id], target.id)

    self.assertEqual(changed, 0)
    self.assertEqual(database.get_folder(child.id).updated_at, before)

def test_move_folders_rejects_moving_into_own_descendant(self):
    parent = database.create_folder("父")
    child = database.create_folder("子", parent_id=parent.id)
    grandchild = database.create_folder("孙", parent_id=child.id)

    with self.assertRaises(ValueError):
        database.move_folders([parent.id], grandchild.id)

    self.assertIsNone(database.get_folder(parent.id).parent_folder_id)
    self.assertEqual(database.get_folder(child.id).parent_folder_id, parent.id)
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：`target_folder_id in get_folder_subtree_ids(ids)` 时抛 `ValueError`；否则 `UPDATE folders SET parent_folder_id=?, updated_at=? WHERE id IN (...) AND parent_folder_id IS NOT ?`。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: 数据库层文件夹批量移动`

### Task 3: 数据库层 delete_folders

**Files:**
- Modify: `app/database.py`
- Test: `tests/test_folder_batch_database.py`

**Interfaces:**
- Consumes: `get_folder_subtree_ids`
- Produces: `database.delete_folders(folder_ids: Iterable[int]) -> int`

- [ ] **Step 1: 写失败测试**

```python
def test_delete_folders_removes_tree_and_keeps_unrelated(self):
    parent = database.create_folder("待删父")
    child = database.create_folder("待删子", parent_id=parent.id)
    database.create_manuscript("父内稿件", "a", folder_id=parent.id)
    database.create_manuscript("子内稿件", "b", folder_id=child.id)
    survivor = database.create_folder("保留")
    survivor_ms = database.create_manuscript("保留稿件", "c", folder_id=survivor.id)

    deleted = database.delete_folders([parent.id, parent.id, 999_999])

    self.assertEqual(deleted, 1)
    self.assertIsNone(database.get_folder(parent.id))
    self.assertIsNone(database.get_folder(child.id))
    self.assertIsNone(database.get_manuscript(parent_manuscript.id))
    self.assertIsNone(database.get_manuscript(child_manuscript.id))
    self.assertIsNotNone(database.get_folder(survivor.id))
    self.assertIsNotNone(database.get_manuscript(survivor_ms.id))

def test_delete_folders_empty_returns_zero(self):
    folder = database.create_folder("保留")
    self.assertEqual(database.delete_folders([]), 0)
    self.assertIsNotNone(database.get_folder(folder.id))
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：单事务内先删 `manuscripts WHERE parent_folder_id IN subtree`，再删 `folders WHERE id IN ids`（子文件夹由 CASCADE 删除），返回 `cursor.rowcount`。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: 数据库层文件夹批量删除`

### Task 4: FolderCard 批量模式支持

**Files:**
- Modify: `app/pages/home_page.py`（FolderCard 类）
- Test: `tests/test_home_page_batch_mode.py`

**Interfaces:**
- Produces: `FolderCard(folder, parent=None, *, batch_mode=False, selected=False)`；`selection_toggled = pyqtSignal(int, bool)`；`is_selected()`；`set_selected(bool)`

- [ ] **Step 1: 写失败测试**

```python
def test_folder_card_checkbox_toggles_selection_in_batch_mode(self):
    folder = database.create_folder("文件夹")
    card = self._track(FolderCard(folder, batch_mode=True, selected=False))
    selected, entered = [], []
    card.selection_toggled.connect(lambda fid, value: selected.append((fid, value)))
    card.folder_clicked.connect(entered.append)

    card.selection_checkbox.click()

    self.assertEqual(selected, [(folder.id, True)])
    self.assertEqual(entered, [])
    self.assertTrue(card.is_selected())

def test_clicking_folder_card_body_toggles_selection_in_batch_mode(self):
    folder = database.create_folder("文件夹")
    card = self._track(FolderCard(folder, batch_mode=True))
    selected = []
    card.selection_toggled.connect(lambda fid, value: selected.append((fid, value)))
    card.show()
    self._app.processEvents()
    QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=QPoint(220, 160))
    self.assertEqual(selected, [(folder.id, True)])

def test_clicking_folder_card_enters_folder_in_normal_mode(self):
    folder = database.create_folder("文件夹")
    card = self._track(FolderCard(folder))
    entered = []
    card.folder_clicked.connect(entered.append)
    card.show()
    self._app.processEvents()
    QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=QPoint(220, 160))
    self.assertEqual(entered, [folder.id])
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：参照 ManuscriptCard——顶部行加复选框、`_batch_mode/_selected/_hovered`、`_apply_card_style`、`set_selected`、`mousePressEvent` 分支。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: 文件夹卡片支持整理模式选择`

### Task 5: HomePage 选择集成

**Files:**
- Modify: `app/pages/home_page.py`
- Test: `tests/test_home_page_batch_mode.py`

**Interfaces:**
- Consumes: `FolderCard` 新接口、`move_folders`、`delete_folders`
- Produces: `HomePage._selected_folder_ids: set[int]`；`_toggle_folder_selection(folder_id, selected)`；`_visible_folder_ids()`

- [ ] **Step 1: 写失败测试**

```python
def test_render_cards_in_batch_mode_shows_folder_checkbox(self):
    database.create_folder("文件夹")
    page = self._create_page()
    page.show()
    self._app.processEvents()
    page._enter_batch_mode()
    self._app.processEvents()
    cards = page._cards_widget.findChildren(FolderCard)
    self.assertTrue(cards)
    self.assertTrue(all(c.selection_checkbox.isVisible() for c in cards))

def test_select_all_includes_folders_and_manuscripts(self):
    folder = database.create_folder("文件夹")
    manuscript = database.create_manuscript("稿件", "body")
    page = self._create_page()
    page._enter_batch_mode()
    page._select_all_visible(True)
    self.assertEqual(page._selected_folder_ids, {folder.id})
    self.assertEqual(page._selected_manuscript_ids, {manuscript.id})

def test_home_page_moves_selected_folders_and_manuscripts(self):
    folder = database.create_folder("移动文件夹")
    manuscript = database.create_manuscript("移动稿件", "body")
    target = database.create_folder("目标")
    page = self._create_page()
    page._enter_batch_mode()
    page._toggle_folder_selection(folder.id, True)
    page._toggle_manuscript_selection(manuscript.id, True)
    moved = page._move_selected_to_folder(target.id)
    self.assertEqual(moved, 2)
    self.assertEqual(database.get_folder(folder.id).parent_folder_id, target.id)
    self.assertEqual(database.get_manuscript(manuscript.id).parent_folder_id, target.id)

def test_home_page_deletes_selected_folders_and_manuscripts(self):
    folder = database.create_folder("删除文件夹")
    database.create_manuscript("文件夹内稿件", "a", folder_id=folder.id)
    manuscript = database.create_manuscript("删除稿件", "b")
    page = self._create_page()
    page._enter_batch_mode()
    page._toggle_folder_selection(folder.id, True)
    page._toggle_manuscript_selection(manuscript.id, True)
    deleted = page._delete_selected_now()
    self.assertEqual(deleted, 2)
    self.assertIsNone(database.get_folder(folder.id))
    self.assertIsNone(database.get_manuscript(manuscript.id))
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：`_selected_folder_ids`；`self._sub_folders`；渲染时传 `batch_mode/selected`；`intersection_update` 两个集合；`_update_batch_bar` 计数合并；`_select_all_visible` 同时选文件夹；`_move_selected_to_folder` 调 `move_folders` + `move_manuscripts`；`_delete_selected_now` 调 `delete_folders` + `delete_manuscripts`；确认消息包含文件夹名。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: 整理模式支持选择文件夹并批量移动/删除`

### Task 6: FolderPickerDialog 禁用子树

**Files:**
- Modify: `app/widgets/batch_management.py`
- Test: `tests/test_batch_management_widgets.py`

**Interfaces:**
- Consumes: `get_folder_subtree_ids`
- Produces: `FolderPickerDialog.set_disabled_folder_ids(disabled: set[int])`

- [ ] **Step 1: 写失败测试**

```python
def test_folder_picker_disables_selected_folder_and_descendants(self):
    parent = database.create_folder("父")
    child = database.create_folder("子", parent_id=parent.id)
    dialog = FolderPickerDialog()

    dialog.set_disabled_folder_ids({parent.id})

    self.assertFalse(dialog.select_folder(parent.id))
    self.assertFalse(dialog.select_folder(child.id))
    self.assertTrue(dialog.select_folder(None))
    self.assertIsNone(dialog.selected_folder_id())
```

- [ ] **Step 2: 运行确认失败**
- [ ] **Step 3: 实现**：`set_disabled_folder_ids` 用 `get_folder_subtree_ids` 展开后存集合；`reload_tree` 时对命中节点 `item.setDisabled(True)`；`select_folder` 跳过禁用项。
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `feat: 移动目标对话框禁用被选文件夹子树`

### Task 7: 回归与最终提交

- [ ] 运行 `python -m pytest tests -q`，确认 38+ 用例全部通过
- [ ] 检查 `Backup/` 各文件备份数量不超过 30 份
- [ ] 最终提交剩余文档与代码
