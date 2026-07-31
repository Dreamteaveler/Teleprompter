# 整理模式文件夹批量选择设计

## 背景

现有整理（批量管理）模式只允许选择讲稿卡片，文件夹卡片保持可见但不参与选择（原设计文档明确列为非目标）。用户希望文件夹也可以被选中，使整理操作覆盖文件夹本身。

## 目标

在整理模式下：

- 文件夹卡片显示复选框，可点击选中/取消；
- 点击文件夹卡片任意位置切换选择状态，不再进入文件夹；
- “全选当前列表”同时选中可见的文件夹和讲稿；
- “已选 N 项”计数包含文件夹和讲稿；
- 批量移动：选中的文件夹整体移入目标文件夹，与讲稿一起处理；
- 批量删除：选中的文件夹递归删除（含内部稿件和子文件夹），与讲稿一起处理；
- 移动目标对话框中，被选中的文件夹及其子孙节点置灰不可选，防止移入自身或子孙。

## 非目标

- 不改变普通模式下文件夹卡片行为（点击进入、右键菜单）；
- 不跨文件夹、面包屑层级或搜索条件保留选择；
- 不引入回收站、软删除或撤销机制；
- 不重构为 Qt Model/View。

## 界面与交互

### FolderCard

- 新增 `selection_toggled = pyqtSignal(int, bool)`；
- 构造参数扩展：`batch_mode: bool = False, selected: bool = False`；
- 批量模式下右上角显示复选框（与 ManuscriptCard 一致），选中/悬停样式沿用金色边框逻辑；
- `mousePressEvent`：批量模式切换复选框；普通模式仍发出 `folder_clicked`；
- 普通模式下右键菜单行为不变。

### HomePage

- 新增 `_selected_folder_ids: set[int]`；
- `_render_cards` 记录当前可见文件夹列表 `self._sub_folders`，渲染 FolderCard 时传入 `batch_mode` 与 `selected`；
- 进入/退出整理模式、切换目录、搜索、Esc 时清空文件夹选择；
- `_select_all_visible`：同时设置文件夹与讲稿选择；
- `_update_batch_bar`：计数为文件夹 + 讲稿；
- 批量删除确认框展示文件夹名与讲稿标题，最多预览 5 项；
- 批量移动：先打开 FolderPickerDialog（禁用已选文件夹子树），确认后移动讲稿与文件夹。

### BatchActionBar

无需改动，文案已使用“已选 N 项”。

### FolderPickerDialog

- 新增 `set_disabled_folder_ids(disabled: set[int])`；
- 被禁用的节点及其全部子孙在树中不可选；
- 若当前选中项被禁用，回退选中根目录。

## 数据库接口

```python
def get_folder_subtree_ids(folder_ids: Iterable[int]) -> set[int]
```

递归收集指定文件夹及其所有子孙的 ID。

```python
def move_folders(
    folder_ids: Iterable[int],
    target_folder_id: int | None,
) -> int
```

- 去重、空集合返回 0；
- 目标为 `None` 表示移动到根目录；
- 目标位于任一被移动文件夹的子树内时抛出 `ValueError`；
- 已在目标位置的文件夹不更新；
- 单事务完成，返回实际移动数量。

```python
def delete_folders(folder_ids: Iterable[int]) -> int
```

- 去重、空集合返回 0；
- 单事务内先删除所有被删文件夹子树内的稿件，再删除文件夹（子文件夹由外键级联删除）；
- 返回实际删除的文件夹数量。

## 数据流

1. 用户进入整理模式；
2. 文件夹卡片发出 `selection_toggled`；
3. `HomePage` 更新 `_selected_folder_ids` 与 `_selected_manuscript_ids`；
4. `BatchActionBar` 更新计数与按钮状态；
5. 移动：`FolderPickerDialog` 禁用子树 → 确认 → `move_manuscripts` + `move_folders`；
6. 删除：确认 → `delete_manuscripts` + `delete_folders`；
7. 成功后退出整理模式并刷新。

## 异常与边界

- 文件夹不能移入自身或子孙（数据库层校验 + UI 禁用双重防护）；
- 无选择时不能触发移动或删除；
- 已存在的 ID 集合中包含已不存在的 ID 时，只处理仍存在的；
- 删除文件夹时，其内部稿件一并永久删除，确认框必须明确提示；
- 批量模式重渲染卡片时保持当前可见选择（文件夹与讲稿）。

## 测试

数据库测试（隔离临时 SQLite）：

- `get_folder_subtree_ids` 覆盖多层子孙；
- `move_folders` 移动到普通文件夹、根目录、已在目标不计、拒绝移入自身/子孙；
- `delete_folders` 递归删除子树稿件与子文件夹、保留无关数据。

界面测试（离屏 Qt）：

- FolderCard 批量模式复选框可见、点击切换、普通模式点击进入文件夹；
- HomePage 整理模式渲染的文件夹卡片复选框可见；
- 全选同时覆盖文件夹与讲稿；
- 批量移动文件夹 + 讲稿；
- 批量删除文件夹 + 讲稿；
- FolderPickerDialog 禁用被选文件夹及其子孙。

回归：现有批量管理、文件夹删除、导航测试全部保持通过。
