# @license
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2024 杭州星奥传媒有限公司（影视飓风）
#
# 本文件基于原始文件（Apache-2.0 许可）进行了修改。
# 本项目基于飞书妙搭平台飓风提词器的源代码重新实现。
# 修改后按 GPL-3.0-or-later 分发。
#
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QFileDialog, QSplitter, QTreeWidget, QTreeWidgetItem,
    QMenu, QInputDialog, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import QFont, QAction, QDragEnterEvent, QDropEvent, QIcon

import os
import re

from app.database import (
    list_manuscripts, search_manuscripts, delete_manuscript, create_manuscript,
    list_folders, get_folder, create_folder, rename_folder, delete_folder,
    get_folder_path, get_all_folders, get_subfolder_count,
    get_manuscript_count_in_folder, move_manuscript, move_manuscripts_batch,
)
from app.models import Manuscript, Folder
from app.docx_importer import import_docx_file
from app.file_importer import import_file
from app.image_utils import compress_images_in_html


CARD_WIDTH = 240
CARD_HEIGHT = 175
SIDEBAR_WIDTH = 220


class ManuscriptCard(QFrame):
    clicked = pyqtSignal(int)
    edit_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)
    play_clicked = pyqtSignal(int)

    def __init__(self, manuscript: Manuscript, parent=None):
        super().__init__(parent)
        self._manuscript = manuscript
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        icon = QLabel("📄")
        icon.setFont(QFont("Segoe UI Emoji", 14))
        top_row.addWidget(icon)
        top_row.addStretch()

        action_btn_style = (
            "QPushButton { background: transparent; border: none; color: #555; padding: 2px 6px; font-size: 11px; }"
            "QPushButton:hover { color: #f2f2f2; }"
        )

        edit_btn = QPushButton("编辑")
        edit_btn.setStyleSheet(action_btn_style)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._manuscript.id))
        top_row.addWidget(edit_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet(
            action_btn_style + "QPushButton:hover { color: #ef4444; }"
        )
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._manuscript.id))
        top_row.addWidget(delete_btn)

        layout.addLayout(top_row)

        title_label = QLabel(manuscript.title if manuscript.title else "未命名稿件")
        title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f2f2f2;")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(44)
        layout.addWidget(title_label)

        preview = manuscript.plain_text_preview(60)
        preview_label = QLabel(preview)
        preview_label.setObjectName("mutedLabel")
        preview_label.setWordWrap(True)
        preview_label.setMinimumHeight(48)
        preview_label.setStyleSheet("color: #9e9e9e; font-size: 11px;")
        layout.addWidget(preview_label, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        date_label = QLabel(manuscript.formatted_date())
        date_label.setStyleSheet("color: #9e9e9e; font-size: 10px;")
        footer.addWidget(date_label)
        footer.addStretch()
        time_label = QLabel(manuscript.estimated_read_time())
        time_label.setStyleSheet("color: #555; font-size: 10px;")
        footer.addWidget(time_label)
        layout.addLayout(footer)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.setStyleSheet("""QFrame#card {
            border-color: rgba(219, 157, 22, 0.5);
            background-color: #171717;
            border-radius: 12px;
        }""")

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.setStyleSheet("""QFrame#card {
            background-color: #141414;
            border: 1px solid #2e2e2e;
            border-radius: 12px;
        }""")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self._manuscript.id)


class FolderSidebar(QFrame):
    folder_selected = pyqtSignal(object)
    root_selected = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar_header = QLabel("  文稿目录")
        sidebar_header.setObjectName("sidebarHeader")
        sidebar_header.setFixedHeight(44)
        sidebar_header.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #9e9e9e; "
            "padding: 12px 16px 4px 16px; border-bottom: 1px solid #2e2e2e;"
        )
        layout.addWidget(sidebar_header)

        self._tree = QTreeWidget()
        self._tree.setObjectName("folderTree")
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tree.setExpandsOnDoubleClick(True)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree, 1)

        btn_row = QWidget()
        btn_row.setObjectName("sidebarFooter")
        btn_row.setStyleSheet(
            "QWidget#sidebarFooter { border-top: 1px solid #2e2e2e; }"
        )
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(8, 6, 8, 6)

        new_folder_btn = QPushButton("+ 新建文件夹")
        new_folder_btn.setObjectName("ghostButton")
        new_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_folder_btn.setStyleSheet(
            "QPushButton { color: #9e9e9e; font-size: 12px; padding: 4px 8px; }"
            "QPushButton:hover { color: #DB9D16; }"
        )
        new_folder_btn.clicked.connect(self._on_new_folder)
        btn_layout.addWidget(new_folder_btn)
        btn_layout.addStretch()
        layout.addWidget(btn_row)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data == "root":
            self.root_selected.emit()
        elif isinstance(data, dict) and data.get("type") == "folder":
            self.folder_selected.emit(data["id"])

    def _on_context_menu(self, pos: QPoint):
        item = self._tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, dict) or data.get("type") != "folder":
            return
        folder_id = data["id"]
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1a1a1a; color: #f2f2f2; border: 1px solid #2e2e2e; border-radius: 6px; padding: 4px; }"
            "QMenu::item { padding: 8px 32px 8px 16px; border-radius: 4px; }"
            "QMenu::item:selected { background-color: #2a2a2a; color: #DB9D16; }"
        )

        rename_action = menu.addAction("✏️ 重命名")
        delete_action = menu.addAction("🗑️ 删除")
        export_action = menu.addAction("📤 导出文件夹")

        action = menu.exec(self._tree.mapToGlobal(pos))
        if action == rename_action:
            self._on_rename_folder(folder_id, item)
        elif action == delete_action:
            self._on_delete_folder(folder_id)
        elif action == export_action:
            self._on_export_folder(folder_id)

    def _on_new_folder(self):
        name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称：")
        if ok and name.strip():
            create_folder(name.strip())
            self.refresh()

    def _on_rename_folder(self, folder_id: int, item: QTreeWidgetItem):
        current = get_folder(folder_id)
        if not current:
            return
        name, ok = QInputDialog.getText(
            self, "重命名文件夹", "新名称：", text=current.name
        )
        if ok and name.strip():
            rename_folder(folder_id, name.strip())
            self.refresh()

    def _on_delete_folder(self, folder_id: int):
        folder = get_folder(folder_id)
        if not folder:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除文件夹「{folder.name}」吗？\n文件夹内的稿件将移回根目录。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_folder(folder_id)
            self.refresh()

    def _on_export_folder(self, folder_id: int):
        folder = get_folder(folder_id)
        if not folder:
            return
        QMessageBox.information(self, "导出文件夹", f"导出功能将在后续版本实现。\n文件夹「{folder.name}」共包含稿件待导出。")

    def refresh(self):
        self._tree.clear()

        root_item = QTreeWidgetItem(self._tree)
        root_item.setText(0, "📂 全部稿件")
        root_item.setData(0, Qt.ItemDataRole.UserRole, "root")
        root_font = root_item.font(0)
        root_font.setBold(True)
        root_item.setFont(0, root_font)

        all_folders = get_all_folders()
        folder_map: dict[int, list[Folder]] = {}
        for f in all_folders:
            parent = f.parent_folder_id if f.parent_folder_id is not None else 0
            if parent not in folder_map:
                folder_map[parent] = []
            folder_map[parent].append(f)

        def _add_children(parent_item: QTreeWidgetItem, parent_id: int):
            children = folder_map.get(parent_id, [])
            for f in children:
                sub_count = get_subfolder_count(f.id)
                ms_count = get_manuscript_count_in_folder(f.id)
                label = f"📁 {f.name}"
                if sub_count > 0 or ms_count > 0:
                    label += f"  ({ms_count})"
                child_item = QTreeWidgetItem(parent_item)
                child_item.setText(0, label)
                child_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "folder", "id": f.id})
                _add_children(child_item, f.id)

        _add_children(root_item, 0)
        root_item.setExpanded(True)

    def select_folder(self, folder_id: int):
        root = self._tree.topLevelItem(0)
        if not root:
            return
        for i in range(root.childCount()):
            child = root.child(i)
            data = child.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, dict) and data.get("id") == folder_id:
                self._tree.setCurrentItem(child)
                return

    def select_root(self):
        root = self._tree.topLevelItem(0)
        if root:
            self._tree.setCurrentItem(root)


class DropOverlay(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropOverlay")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "QLabel#dropOverlay {"
            "  background-color: rgba(13, 13, 13, 0.92);"
            "  color: #DB9D16;"
            "  font-size: 20px;"
            "  font-weight: bold;"
            "  border: 3px dashed #DB9D16;"
            "  border-radius: 16px;"
            "}"
        )
        self.hide()


class FolderEntryWidget(QFrame):
    folder_clicked = pyqtSignal(int)

    def __init__(self, folder: Folder, parent=None):
        super().__init__(parent)
        self._folder = folder
        self.setObjectName("folderEntry")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_WIDTH, 80)
        self.setStyleSheet(
            "QFrame#folderEntry { background-color: #141414; border: 1px solid #2e2e2e; border-radius: 12px; }"
            "QFrame#folderEntry:hover { border-color: rgba(219, 157, 22, 0.5); background-color: #171717; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        icon_row = QHBoxLayout()
        icon = QLabel("📁")
        icon.setFont(QFont("Segoe UI Emoji", 20))
        icon_row.addWidget(icon)
        icon_row.addStretch()

        ms_count = get_manuscript_count_in_folder(folder.id)
        count_label = QLabel(str(ms_count))
        count_label.setStyleSheet("color: #9e9e9e; font-size: 11px;")
        icon_row.addWidget(count_label)
        layout.addLayout(icon_row)

        name_label = QLabel(folder.name)
        name_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #f2f2f2;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.folder_clicked.emit(self._folder.id)


class HomePage(QWidget):
    navigate_to_prompter = pyqtSignal(int)
    navigate_to_editor = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manuscripts: list[Manuscript] = []
        self._current_folder_id: int | None = None
        self._folder_path: list[Folder] = []
        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.timeout.connect(self._render_cards)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background-color: #2e2e2e; }")

        self._sidebar = FolderSidebar()
        self._sidebar.folder_selected.connect(self._on_folder_selected)
        self._sidebar.root_selected.connect(self._on_root_selected)
        splitter.addWidget(self._sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(72)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 24, 12)

        logo = QLabel("提词器")
        logo.setStyleSheet("font-size: 18px; font-weight: 700; color: #f2f2f2;")
        header_layout.addWidget(logo)

        header_layout.addStretch()

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchField")
        self._search_input.setPlaceholderText("🔍 搜索稿件...")
        self._search_input.setFixedWidth(260)
        self._search_input.setFixedHeight(36)
        self._search_input.textChanged.connect(self._on_search)
        header_layout.addWidget(self._search_input)

        import_btn = QPushButton("+ 新建稿件")
        import_btn.setObjectName("ghostButton")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.clicked.connect(lambda: self.navigate_to_editor.emit(None))
        header_layout.addWidget(import_btn)

        new_btn = QPushButton("📄 导入文件")
        new_btn.setObjectName("accentButton")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._import_file_dialog)
        header_layout.addWidget(new_btn)

        content_layout.addWidget(header)

        self._breadcrumb = QWidget()
        self._breadcrumb.setFixedHeight(36)
        self._breadcrumb.setStyleSheet(
            "QWidget#breadcrumb { background-color: transparent; }"
        )
        breadcrumb_layout = QHBoxLayout(self._breadcrumb)
        breadcrumb_layout.setContentsMargins(40, 4, 40, 4)
        breadcrumb_layout.setSpacing(4)
        breadcrumb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self._breadcrumb)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scroll_content = QWidget()
        self._scroll_content.setAcceptDrops(True)
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(40, 16, 40, 24)
        self._scroll_layout.setSpacing(16)

        self._folder_entries_widget = QWidget()
        self._folder_entries_layout = QHBoxLayout(self._folder_entries_widget)
        self._folder_entries_layout.setSpacing(12)
        self._folder_entries_layout.setContentsMargins(0, 0, 0, 0)
        self._folder_entries_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._scroll_layout.addWidget(self._folder_entries_widget)

        self._count_label = QLabel("全部稿件")
        self._count_label.setObjectName("sectionTitle")
        self._scroll_layout.addWidget(self._count_label)

        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.addWidget(self._cards_widget)
        self._scroll_layout.addStretch()

        scroll.setWidget(self._scroll_content)
        content_layout.addWidget(scroll, 1)

        splitter.addWidget(content)
        splitter.setSizes([SIDEBAR_WIDTH, 800])
        outer.addWidget(splitter)

        self._drop_overlay = DropOverlay(self)
        self._drop_overlay.hide()
        self.setAcceptDrops(True)

    def _on_folder_selected(self, folder_id: int):
        self._current_folder_id = folder_id
        self._search_input.clear()
        self._folder_path = get_folder_path(folder_id)
        self._update_breadcrumb()
        self._refresh()

    def _on_root_selected(self):
        self._current_folder_id = None
        self._search_input.clear()
        self._folder_path = []
        self._update_breadcrumb()
        self._refresh()

    def _on_breadcrumb_click(self, folder_id: int | None):
        self._current_folder_id = folder_id
        self._search_input.clear()
        if folder_id is not None:
            self._folder_path = get_folder_path(folder_id)
        else:
            self._folder_path = []
        self._update_breadcrumb()
        self._refresh()

    def _update_breadcrumb(self):
        clear_layout = self._breadcrumb.layout()
        if clear_layout is None:
            return
        while clear_layout.count():
            item = clear_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        arrow_style = "color: #555; font-size: 12px; padding: 0 4px; background: transparent; border: none;"

        root_btn = QPushButton("📂 全部稿件")
        root_btn.setObjectName("breadcrumbBtn")
        root_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        root_btn.setStyleSheet(
            "QPushButton { color: %s; background: transparent; border: none; font-size: 12px; padding: 2px 6px; }"
            "QPushButton:hover { color: #DB9D16; }" % (
                "#DB9D16" if self._current_folder_id is None else "#9e9e9e"
            )
        )
        root_btn.clicked.connect(lambda: self._on_breadcrumb_click(None))
        clear_layout.addWidget(root_btn)

        for i, f in enumerate(self._folder_path):
            arrow = QLabel("▸")
            arrow.setStyleSheet(arrow_style)
            clear_layout.addWidget(arrow)

            is_last = (i == len(self._folder_path) - 1)
            btn = QPushButton(f"📁 {f.name}")
            btn.setObjectName("breadcrumbBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { color: %s; background: transparent; border: none; font-size: 12px; padding: 2px 6px; }"
                "QPushButton:hover { color: #DB9D16; }" % (
                    "#DB9D16" if is_last else "#9e9e9e"
                )
            )
            bid = f.id
            btn.clicked.connect(lambda checked=False, fid=bid: self._on_breadcrumb_click(fid))
            clear_layout.addWidget(btn)

            if not is_last:
                folder_menu_btn = QPushButton("▼")
                folder_menu_btn.setObjectName("breadcrumbBtn")
                folder_menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                folder_menu_btn.setStyleSheet(
                    "QPushButton { color: #9e9e9e; background: transparent; border: none; font-size: 9px; padding: 2px 4px; }"
                    "QPushButton:hover { color: #DB9D16; }"
                )
                fid = f.id
                folder_menu_btn.clicked.connect(
                    lambda checked=False, folder_id=fid, w=folder_menu_btn: self._show_folder_menu(folder_id, w)
                )
                clear_layout.addWidget(folder_menu_btn)

        clear_layout.addStretch()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                HomePage._clear_layout(child.layout())

    def _show_folder_menu(self, folder_id: int, anchor_widget: QPushButton):
        folder = get_folder(folder_id)
        if not folder:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1a1a1a; color: #f2f2f2; border: 1px solid #2e2e2e; border-radius: 6px; padding: 4px; }"
            "QMenu::item { padding: 8px 32px 8px 16px; border-radius: 4px; }"
            "QMenu::item:selected { background-color: #2a2a2a; color: #DB9D16; }"
        )
        rename_action = menu.addAction("✏️ 重命名")
        new_child_action = menu.addAction("📁 新建子文件夹")
        delete_action = menu.addAction("🗑️ 删除")

        action = menu.exec(anchor_widget.mapToGlobal(QPoint(0, anchor_widget.height())))
        if action == rename_action:
            name, ok = QInputDialog.getText(self, "重命名文件夹", "新名称：", text=folder.name)
            if ok and name.strip():
                rename_folder(folder_id, name.strip())
                self._refresh()
        elif action == new_child_action:
            name, ok = QInputDialog.getText(self, "新建子文件夹", "文件夹名称：")
            if ok and name.strip():
                create_folder(name.strip(), parent_id=folder_id)
                self._refresh()
        elif action == delete_action:
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除文件夹「{folder.name}」吗？\n文件夹内的稿件将移回根目录。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                delete_folder(folder_id)
                self._on_root_selected()
                self._refresh()

    def _import_file_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "导入文件", "",
            "支持的文件 (*.docx *.txt *.md);;Word 文档 (*.docx);;文本文件 (*.txt);;Markdown (*.md)"
        )
        if not filepath:
            return
        self._import_single_file(filepath)

    def _import_single_file(self, filepath: str, auto_confirm: bool = False):
        try:
            from app.file_importer import import_file
            title, html_content, needs_confirm = import_file(filepath, auto_confirm_formulas=auto_confirm)
            if not html_content:
                QMessageBox.warning(self, "导入失败", "无法读取文档内容。")
                return

            if needs_confirm and not auto_confirm:
                has_formulas = bool(re.search(r'<img[^>]*class="formula"', html_content, re.IGNORECASE) or
                                    re.search(r'\$', html_content))
                has_images = bool(re.search(r'<img[^>]*>', html_content, re.IGNORECASE))

                msg = "检测到"
                parts = []
                if has_formulas:
                    parts.append("公式")
                if has_images:
                    parts.append("图片")
                msg += "和".join(parts) + "，是否转换格式以保证正确渲染？"

                reply = QMessageBox.question(
                    self, "转换提示", msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                title, html_content, _ = import_file(filepath, auto_confirm_formulas=True)

            html_content = compress_images_in_html(html_content)
            manuscript = create_manuscript(title, html_content, folder_id=self._current_folder_id)
            self.navigate_to_editor.emit(manuscript)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"无法导入文件：\n{e}")

    def _on_search(self, text: str):
        if text.strip():
            self._manuscripts = search_manuscripts(text.strip(), folder_id=self._current_folder_id)
        else:
            self._manuscripts = list_manuscripts(folder_id=self._current_folder_id)
        self._render_cards()

    def _refresh(self):
        self._manuscripts = list_manuscripts(folder_id=self._current_folder_id)
        self._sidebar.refresh()
        if self._current_folder_id is not None:
            self._sidebar.select_folder(self._current_folder_id)
        else:
            self._sidebar.select_root()
        self._render_cards()

    def _render_cards(self):
        clear_layout = self._folder_entries_layout
        while clear_layout.count():
            item = clear_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._current_folder_id is not None:
            sub_folders = list_folders(parent_id=self._current_folder_id)
        else:
            sub_folders = list_folders(parent_id=None)

        for sf in sub_folders:
            entry = FolderEntryWidget(sf)
            entry.folder_clicked.connect(self._on_folder_selected)
            self._folder_entries_layout.addWidget(entry)
        self._folder_entries_widget.setVisible(len(sub_folders) > 0)

        old_widget = self._cards_widget
        old_widget.hide()
        self._scroll_layout.removeWidget(old_widget)
        old_widget.deleteLater()

        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.insertWidget(2, self._cards_widget)

        count = len(self._manuscripts)
        if self._current_folder_id is not None:
            folder = get_folder(self._current_folder_id)
            label = f"「{folder.name}」中的稿件（共 {count} 条）" if folder else f"稿件（共 {count} 条）"
        else:
            label = f"全部稿件（共 {count} 条）"
        self._count_label.setText(label)

        if count == 0:
            empty = QWidget()
            empty.setAcceptDrops(True)
            empty_layout = QVBoxLayout(empty)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.setSpacing(16)

            icon = QLabel("📄")
            icon.setFont(QFont("Segoe UI Emoji", 48))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(icon)

            msg = QLabel("暂无稿件\n拖放文件到此处导入，或点击右上角「新建稿件」开始创作")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setObjectName("mutedLabel")
            msg.setStyleSheet("font-size: 15px; line-height: 1.8;")
            empty_layout.addWidget(msg)

            self._cards_layout.addWidget(empty)
            return

        row_layout = None
        card_spacing = 12
        win = self.window()
        available_width = (win.width() if win else 1280) - 300
        if available_width <= 100:
            available_width = 1100
        row_width = 0

        for ms in self._manuscripts:
            if row_layout is None or row_width + CARD_WIDTH > available_width:
                if row_layout is not None:
                    row_layout.addStretch()
                row_layout = QHBoxLayout()
                row_layout.setSpacing(card_spacing)
                row_layout.setContentsMargins(0, 0, 0, 0)
                self._cards_layout.addLayout(row_layout)
                row_width = 0

            card = ManuscriptCard(ms)
            card.play_clicked.connect(self.navigate_to_prompter.emit)
            card.edit_clicked.connect(lambda mid: self.navigate_to_editor.emit(
                next((m for m in self._manuscripts if m.id == mid), None)
            ))
            card.delete_clicked.connect(self._confirm_delete)
            row_layout.addWidget(card)
            row_width += CARD_WIDTH + card_spacing

        if row_layout is not None:
            row_layout.addStretch()
        self._cards_layout.addStretch()

    def _confirm_delete(self, manuscript_id: int):
        ms = next((m for m in self._manuscripts if m.id == manuscript_id), None)
        if not ms:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除稿件「{ms.title or '未命名'}」吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            delete_manuscript(manuscript_id)
            self._refresh()

    def refresh(self):
        self._search_input.clear()
        self._on_root_selected()
        self._refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_drop_overlay'):
            self._drop_overlay.setGeometry(self.rect())
        if hasattr(self, '_relayout_timer'):
            self._relayout_timer.start(150)

    # ─── 拖放支持 ───────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            paths = [u.toLocalFile() for u in urls]
            has_folder = any(os.path.isdir(p) for p in paths)
            has_file = any(os.path.isfile(p) for p in paths)

            if has_folder:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
                self._drop_overlay.setText("📂 释放以导入文件夹\n（公式/图片将自动处理）")
                self._drop_overlay.setGeometry(self.rect())
                self._drop_overlay.show()
            elif has_file:
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
                if len(paths) == 1:
                    self._drop_overlay.setText("📄 释放以导入文件")
                else:
                    self._drop_overlay.setText(f"📄 释放以导入 {len(paths)} 个文件")
                self._drop_overlay.setGeometry(self.rect())
                self._drop_overlay.show()
            else:
                event.ignore()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_overlay.hide()

    def dropEvent(self, event: QDropEvent):
        self._drop_overlay.hide()
        if not event.mimeData().hasUrls():
            return

        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls]
        folders = [p for p in paths if os.path.isdir(p)]
        files = [p for p in paths if os.path.isfile(p)]

        if folders:
            for folder_path in folders:
                self._import_folder(folder_path)
            self._refresh()

        elif len(files) == 1:
            self._import_single_file(files[0])

        elif files:
            self._import_files_batch(files)
            self._refresh()

    def _import_folder(self, folder_path: str):
        folder_name = os.path.basename(folder_path)
        new_folder = create_folder(folder_name, parent_id=self._current_folder_id, folder_type="import")

        imported = 0
        for root, dirs, filenames in os.walk(folder_path):
            for fname in filenames:
                fpath = os.path.join(root, fname)
                if not os.path.isfile(fpath):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                if ext not in (".docx", ".txt", ".md", ".markdown"):
                    continue
                try:
                    title, html_content, _ = import_file(fpath, auto_confirm_formulas=True)
                    if html_content:
                        html_content = compress_images_in_html(html_content)
                        create_manuscript(title, html_content, folder_id=new_folder.id)
                        imported += 1
                except Exception:
                    pass

        if imported > 0:
            QMessageBox.information(
                self, "导入完成",
                f"已导入 {imported} 个文件到文件夹「{folder_name}」。"
            )

    def _import_files_batch(self, filepaths: list[str]):
        imported = 0
        for fpath in filepaths:
            if not os.path.isfile(fpath):
                continue
            ext = os.path.splitext(fpath)[1].lower()
            if ext not in (".docx", ".txt", ".md", ".markdown"):
                continue
            try:
                title, html_content, _ = import_file(fpath, auto_confirm_formulas=True)
                if html_content:
                    html_content = compress_images_in_html(html_content)
                    create_manuscript(title, html_content, folder_id=self._current_folder_id)
                    imported += 1
            except Exception:
                pass

        if imported > 0:
            QMessageBox.information(self, "导入完成", f"已导入 {imported} 个文件。")
