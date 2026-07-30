# @license
# SPDX-License-Identifier: GPL-3.0-or-later
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from app.database import create_folder, get_all_folders
from app.models import Folder


ROOT_FOLDER = -1


class BatchActionBar(QFrame):
    select_all_toggled = pyqtSignal(bool)
    move_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("batchActionBar")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(40, 8, 40, 8)
        layout.setSpacing(10)

        self.context_label = QLabel("全部稿件")
        self.context_label.setObjectName("toolbarContext")
        self.context_label.setMaximumWidth(180)
        layout.addWidget(self.context_label)

        self.filter_label = QLabel()
        self.filter_label.setObjectName("filterHint")
        self.filter_label.setMaximumWidth(140)
        self.filter_label.hide()
        layout.addWidget(self.filter_label)

        self.select_all_checkbox = QCheckBox("全选当前列表")
        self.select_all_checkbox.stateChanged.connect(
            self._on_select_all_state_changed
        )
        layout.addWidget(self.select_all_checkbox)

        self.count_label = QLabel("已选 0 项")
        self.count_label.setObjectName("accentLabel")
        layout.addWidget(self.count_label)
        layout.addStretch()

        self.move_button = QPushButton("移入文件夹")
        self.move_button.setObjectName("ghostButton")
        self.move_button.clicked.connect(
            lambda checked=False: self.move_requested.emit()
        )
        layout.addWidget(self.move_button)

        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(
            lambda checked=False: self.delete_requested.emit()
        )
        layout.addWidget(self.delete_button)

        self.exit_button = QPushButton("完成")
        self.exit_button.setObjectName("ghostButton")
        self.exit_button.clicked.connect(
            lambda checked=False: self.exit_requested.emit()
        )
        layout.addWidget(self.exit_button)

        self.set_selection_state(selected_count=0, visible_count=0)

    def _on_select_all_state_changed(self, state: int):
        self.select_all_toggled.emit(state == Qt.CheckState.Checked.value)

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

    def set_selection_state(self, selected_count: int, visible_count: int):
        self.count_label.setText(f"已选 {selected_count} 项")
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

        was_blocked = self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setCheckState(state)
        self.select_all_checkbox.blockSignals(was_blocked)


class FolderPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("移动到文件夹")
        self.setMinimumSize(420, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("选择目标文件夹")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        hint = QLabel("可以选择根目录或任意子文件夹。")
        hint.setObjectName("mutedLabel")
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setObjectName("folderTree")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(22)
        layout.addWidget(self.tree, 1)

        create_row = QHBoxLayout()
        create_row.addStretch()
        self.new_folder_button = QPushButton("新建文件夹")
        self.new_folder_button.setObjectName("ghostButton")
        self.new_folder_button.clicked.connect(self._prompt_create_folder)
        create_row.addWidget(self.new_folder_button)
        layout.addLayout(create_row)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText(
            "移动到这里"
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "取消"
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.reload_tree()

    def reload_tree(self, select_folder_id: int | None = None):
        self.tree.clear()
        root_item = QTreeWidgetItem(["📂 全部稿件（根目录）"])
        root_item.setData(0, Qt.ItemDataRole.UserRole, ROOT_FOLDER)
        self.tree.addTopLevelItem(root_item)

        folders = get_all_folders()
        items: dict[int, QTreeWidgetItem] = {}
        for folder in folders:
            item = QTreeWidgetItem([f"📁 {folder.name}"])
            item.setData(0, Qt.ItemDataRole.UserRole, folder.id)
            items[folder.id] = item

        for folder in folders:
            parent_item = items.get(folder.parent_folder_id, root_item)
            parent_item.addChild(items[folder.id])

        self.tree.expandAll()
        self.select_folder(select_folder_id)

    def _iter_tree_items(self):
        pending = [
            self.tree.topLevelItem(index)
            for index in range(self.tree.topLevelItemCount())
        ]
        while pending:
            item = pending.pop(0)
            yield item
            pending[0:0] = [
                item.child(index) for index in range(item.childCount())
            ]

    def select_folder(self, folder_id: int | None) -> bool:
        target = ROOT_FOLDER if folder_id is None else folder_id
        for item in self._iter_tree_items():
            if item.data(0, Qt.ItemDataRole.UserRole) == target:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                return True
        return False

    def selected_folder_id(self) -> int | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        folder_id = item.data(0, Qt.ItemDataRole.UserRole)
        if folder_id == ROOT_FOLDER:
            return None
        return int(folder_id)

    def create_folder_under_selection(self, name: str) -> Folder:
        normalized = name.strip()
        if not normalized:
            raise ValueError("文件夹名称不能为空")
        folder = create_folder(
            normalized,
            parent_id=self.selected_folder_id(),
        )
        self.reload_tree(select_folder_id=folder.id)
        return folder

    def _prompt_create_folder(self):
        name, accepted = QInputDialog.getText(
            self,
            "新建文件夹",
            "文件夹名称：",
        )
        if not accepted:
            return
        try:
            self.create_folder_under_selection(name)
        except Exception as error:
            QMessageBox.warning(
                self,
                "创建失败",
                f"无法创建文件夹：\n{error}",
            )
