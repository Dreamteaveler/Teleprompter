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
    QFileDialog, QMenu, QInputDialog, QCheckBox, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPoint
from PyQt6.QtGui import (
    QFont, QAction, QDragEnterEvent, QDropEvent,
)

import os
import re

from app.database import (
    list_manuscripts, search_manuscripts, delete_manuscript,
    delete_manuscripts, create_manuscript,
    list_folders, get_folder, create_folder, rename_folder, delete_folder,
    get_folder_path, get_manuscript_count_in_folder, move_manuscripts,
)
from app.models import Manuscript, Folder
from app.file_importer import import_file
from app.html_cleaner import clean_imported_html
from app.image_utils import compress_images_in_html
from app.widgets.batch_management import BatchActionBar, FolderPickerDialog


CARD_WIDTH = 240
CARD_HEIGHT = 175


class ManuscriptCard(QFrame):
    clicked = pyqtSignal(int)
    edit_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)
    play_clicked = pyqtSignal(int)
    selection_toggled = pyqtSignal(int, bool)

    def __init__(
        self,
        manuscript: Manuscript,
        parent=None,
        *,
        batch_mode: bool = False,
        selected: bool = False,
    ):
        super().__init__(parent)
        self._manuscript = manuscript
        self._batch_mode = batch_mode
        self._selected = selected
        self._hovered = False
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        self.selection_checkbox = QCheckBox()
        self.selection_checkbox.setToolTip("选择这篇讲稿")
        self.selection_checkbox.setAccessibleName(
            f"选择讲稿：{manuscript.title or '未命名稿件'}"
        )
        self.selection_checkbox.setVisible(batch_mode)
        self.selection_checkbox.toggled.connect(
            self._on_selection_checkbox_toggled
        )
        top_row.addWidget(self.selection_checkbox)

        icon = QLabel("📄")
        icon.setFont(QFont("Segoe UI Emoji", 14))
        top_row.addWidget(icon)
        top_row.addStretch()

        action_btn_style = (
            "QPushButton { background: transparent; border: none; color: #555; padding: 2px 6px; font-size: 11px; }"
            "QPushButton:hover { color: #f2f2f2; }"
        )

        self._edit_button = QPushButton("编辑")
        self._edit_button.setStyleSheet(action_btn_style)
        self._edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_button.clicked.connect(
            lambda: self.edit_clicked.emit(self._manuscript.id)
        )
        self._edit_button.setVisible(not batch_mode)
        top_row.addWidget(self._edit_button)

        self._delete_button = QPushButton("删除")
        self._delete_button.setStyleSheet(
            action_btn_style + "QPushButton:hover { color: #ef4444; }"
        )
        self._delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_button.clicked.connect(
            lambda: self.delete_clicked.emit(self._manuscript.id)
        )
        self._delete_button.setVisible(not batch_mode)
        top_row.addWidget(self._delete_button)

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

        self.set_selected(selected)

    def _on_selection_checkbox_toggled(self, selected: bool):
        self._selected = selected
        self._apply_card_style()
        self.selection_toggled.emit(self._manuscript.id, selected)

    def is_selected(self) -> bool:
        return self._selected

    def set_selected(self, selected: bool):
        self._selected = selected
        was_blocked = self.selection_checkbox.blockSignals(True)
        self.selection_checkbox.setChecked(selected)
        self.selection_checkbox.blockSignals(was_blocked)
        self._apply_card_style()

    def _apply_card_style(self):
        if self._selected:
            border = "2px solid #DB9D16"
            background = "rgba(219, 157, 22, 0.12)"
        elif self._hovered:
            border = "1px solid rgba(219, 157, 22, 0.5)"
            background = "#171717"
        else:
            border = "1px solid #2e2e2e"
            background = "#141414"
        self.setStyleSheet(
            f"""QFrame#card {{
                background-color: {background};
                border: {border};
                border-radius: 12px;
            }}"""
        )

    def enterEvent(self, event):
        super().enterEvent(event)
        self._hovered = True
        self._apply_card_style()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hovered = False
        self._apply_card_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._batch_mode:
                self.selection_checkbox.toggle()
            else:
                self.play_clicked.emit(self._manuscript.id)
            event.accept()
            return
        super().mousePressEvent(event)


class FolderCard(QFrame):
    folder_clicked = pyqtSignal(int)
    folder_context_menu = pyqtSignal(int, QPoint)

    def __init__(self, folder: Folder, parent=None):
        super().__init__(parent)
        self._folder = folder
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.folder_context_menu.emit(self._folder.id, self.mapToGlobal(pos))
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(0)

        icon_row = QHBoxLayout()
        icon = QLabel("📁")
        icon.setFont(QFont("Segoe UI Emoji", 28))
        icon_row.addWidget(icon)
        icon_row.addStretch()

        ms_count = get_manuscript_count_in_folder(folder.id)
        count_label = QLabel(str(ms_count))
        count_label.setStyleSheet("color: #9e9e9e; font-size: 11px; background: transparent;")
        icon_row.addWidget(count_label)
        layout.addLayout(icon_row)

        name_label = QLabel(folder.name)
        name_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f2f2f2;")
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(44)
        layout.addWidget(name_label)

        date_label = QLabel(folder.formatted_date())
        date_label.setStyleSheet("color: #9e9e9e; font-size: 10px; background: transparent;")
        layout.addWidget(date_label)
        layout.addStretch()

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
            self.folder_clicked.emit(self._folder.id)


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


class HomePage(QWidget):
    navigate_to_prompter = pyqtSignal(int)
    navigate_to_editor = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manuscripts: list[Manuscript] = []
        self._current_folder_id: int | None = None
        self._folder_path: list[Folder] = []
        self._batch_mode = False
        self._selected_manuscript_ids: set[int] = set()
        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.timeout.connect(self._render_cards)
        self._init_ui()
        self._refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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

        self._batch_manage_button = QPushButton("批量管理")
        self._batch_manage_button.setObjectName("ghostButton")
        self._batch_manage_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self._batch_manage_button.clicked.connect(self._toggle_batch_mode)
        header_layout.addWidget(self._batch_manage_button)

        new_folder_btn = QPushButton("📁 新建文件夹")
        new_folder_btn.setObjectName("ghostButton")
        new_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_folder_btn.clicked.connect(self._on_new_folder)
        header_layout.addWidget(new_folder_btn)

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

        layout.addWidget(header)

        self._breadcrumb = QWidget()
        self._breadcrumb.setFixedHeight(36)
        self._breadcrumb.setStyleSheet(
            "QWidget { background-color: transparent; }"
        )
        breadcrumb_layout = QHBoxLayout(self._breadcrumb)
        breadcrumb_layout.setContentsMargins(40, 4, 40, 4)
        breadcrumb_layout.setSpacing(4)
        breadcrumb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._breadcrumb)

        self._batch_bar = BatchActionBar()
        self._batch_bar.select_all_toggled.connect(self._select_all_visible)
        self._batch_bar.move_requested.connect(
            self._move_selected_manuscripts
        )
        self._batch_bar.delete_requested.connect(
            self._delete_selected_manuscripts
        )
        self._batch_bar.exit_requested.connect(self._exit_batch_mode)
        self._batch_bar.hide()
        layout.addWidget(self._batch_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scroll_content = QWidget()
        self._scroll_content.setAcceptDrops(True)
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(40, 16, 40, 24)
        self._scroll_layout.setSpacing(16)

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
        layout.addWidget(scroll, 1)

        self._drop_overlay = DropOverlay(self)
        self._drop_overlay.hide()
        self.setAcceptDrops(True)

    def _toggle_batch_mode(self, checked: bool = False):
        if self._batch_mode:
            self._exit_batch_mode()
        else:
            self._enter_batch_mode()

    def _enter_batch_mode(self):
        if self._batch_mode:
            return
        self._batch_mode = True
        self._selected_manuscript_ids.clear()
        self._batch_bar.show()
        self._batch_manage_button.setText("退出批量管理")
        self._render_cards()

    def _exit_batch_mode(self, render: bool = True):
        was_active = self._batch_mode or bool(
            self._selected_manuscript_ids
        )
        self._batch_mode = False
        self._selected_manuscript_ids.clear()
        self._batch_bar.hide()
        self._batch_manage_button.setText("批量管理")
        if render and was_active:
            self._render_cards()

    def _visible_manuscript_ids(self) -> set[int]:
        return {manuscript.id for manuscript in self._manuscripts}

    def _update_batch_bar(self):
        self._batch_bar.set_selection_state(
            selected_count=len(self._selected_manuscript_ids),
            visible_count=len(self._manuscripts),
        )

    def _toggle_manuscript_selection(
        self,
        manuscript_id: int,
        selected: bool,
    ):
        if manuscript_id not in self._visible_manuscript_ids():
            return
        if selected:
            self._selected_manuscript_ids.add(manuscript_id)
        else:
            self._selected_manuscript_ids.discard(manuscript_id)
        self._update_batch_bar()

    def _select_all_visible(self, selected: bool):
        if not self._batch_mode:
            return
        if selected:
            self._selected_manuscript_ids = (
                self._visible_manuscript_ids()
            )
        else:
            self._selected_manuscript_ids.clear()
        self._render_cards()

    def _on_new_folder(self):
        name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称：")
        if ok and name.strip():
            create_folder(name.strip(), parent_id=self._current_folder_id)
            self._refresh()

    def _on_folder_selected(self, folder_id: int):
        self._exit_batch_mode(render=False)
        self._current_folder_id = folder_id
        self._search_input.clear()
        self._folder_path = get_folder_path(folder_id)
        self._update_breadcrumb()
        self._refresh()

    def _on_root_selected(self):
        self._exit_batch_mode(render=False)
        self._current_folder_id = None
        self._search_input.clear()
        self._folder_path = []
        self._update_breadcrumb()
        self._refresh()

    def _on_breadcrumb_click(self, folder_id: int | None):
        self._exit_batch_mode(render=False)
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
            self._confirm_delete_folder(folder_id)

    def _on_folder_card_context_menu(self, folder_id: int, global_pos: QPoint):
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
        delete_action = menu.addAction("🗑️ 删除")

        action = menu.exec(global_pos)
        if action == rename_action:
            name, ok = QInputDialog.getText(self, "重命名文件夹", "新名称：", text=folder.name)
            if ok and name.strip():
                rename_folder(folder_id, name.strip())
                self._refresh()
        elif action == delete_action:
            self._confirm_delete_folder(folder_id)

    def _confirm_delete_folder(self, folder_id: int):
        folder = get_folder(folder_id)
        if not folder:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除文件夹「{folder.name}」吗？\n"
            "文件夹内的所有稿件和子文件夹也将被永久删除，此操作不可撤销。",
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

            html_content = clean_imported_html(html_content)
            html_content = compress_images_in_html(html_content)
            manuscript = create_manuscript(title, html_content, folder_id=self._current_folder_id)
            self.navigate_to_editor.emit(manuscript)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"无法导入文件：\n{e}")

    def _on_search(self, text: str):
        self._exit_batch_mode(render=False)
        if text.strip():
            self._manuscripts = search_manuscripts(text.strip(), folder_id=self._current_folder_id)
        else:
            self._manuscripts = list_manuscripts(folder_id=self._current_folder_id)
        self._render_cards()

    def _refresh(self):
        self._manuscripts = list_manuscripts(folder_id=self._current_folder_id)
        self._update_breadcrumb()
        self._render_cards()

    def _render_cards(self):
        if self._current_folder_id is not None:
            sub_folders = list_folders(parent_id=self._current_folder_id)
        else:
            sub_folders = list_folders(parent_id=None)

        self._selected_manuscript_ids.intersection_update(
            self._visible_manuscript_ids()
        )

        old_widget = self._cards_widget
        old_widget.hide()
        self._scroll_layout.removeWidget(old_widget)
        old_widget.deleteLater()

        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.insertWidget(1, self._cards_widget)

        total_items = len(sub_folders) + len(self._manuscripts)
        if self._current_folder_id is not None:
            folder = get_folder(self._current_folder_id)
            label = f"「{folder.name}」（共 {total_items} 项）" if folder else f"（共 {total_items} 项）"
        else:
            label = f"全部稿件（共 {total_items} 项）"
        self._count_label.setText(label)

        if total_items == 0:
            empty = QWidget()
            empty.setAcceptDrops(True)
            empty_layout = QVBoxLayout(empty)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.setSpacing(16)

            icon = QLabel("📄")
            icon.setFont(QFont("Segoe UI Emoji", 48))
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(icon)

            msg = QLabel("暂无内容\n拖放文件到此处导入，或点击右上角按钮创建")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setObjectName("mutedLabel")
            msg.setStyleSheet("font-size: 15px; line-height: 1.8;")
            empty_layout.addWidget(msg)

            self._cards_layout.addWidget(empty)
            self._update_batch_bar()
            return

        items = []
        for f in sub_folders:
            items.append(("folder", f))
        for ms in self._manuscripts:
            items.append(("manuscript", ms))

        items.sort(key=lambda x: x[1].updated_at if x[1].updated_at else "", reverse=True)

        row_layout = None
        card_spacing = 12
        win = self.window()
        available_width = (win.width() if win else 1280) - 80
        if available_width <= 100:
            available_width = 1100
        row_width = 0

        for item_type, item in items:
            if row_layout is None or row_width + CARD_WIDTH > available_width:
                if row_layout is not None:
                    row_layout.addStretch()
                row_layout = QHBoxLayout()
                row_layout.setSpacing(card_spacing)
                row_layout.setContentsMargins(0, 0, 0, 0)
                self._cards_layout.addLayout(row_layout)
                row_width = 0

            if item_type == "folder":
                card = FolderCard(item)
                card.folder_clicked.connect(self._on_folder_selected)
                card.folder_context_menu.connect(self._on_folder_card_context_menu)
            else:
                card = ManuscriptCard(
                    item,
                    batch_mode=self._batch_mode,
                    selected=item.id in self._selected_manuscript_ids,
                )
                card.play_clicked.connect(self.navigate_to_prompter.emit)
                card.edit_clicked.connect(lambda mid: self.navigate_to_editor.emit(
                    next((m for m in self._manuscripts if m.id == mid), None)
                ))
                card.delete_clicked.connect(self._confirm_delete)
                card.selection_toggled.connect(
                    self._toggle_manuscript_selection
                )

            row_layout.addWidget(card)
            row_width += CARD_WIDTH + card_spacing

        if row_layout is not None:
            row_layout.addStretch()
        self._cards_layout.addStretch()
        self._update_batch_bar()

    def _move_selected_to_folder(
        self,
        target_folder_id: int | None,
    ) -> int:
        manuscript_ids = tuple(self._selected_manuscript_ids)
        if not manuscript_ids:
            return 0
        moved = move_manuscripts(manuscript_ids, target_folder_id)
        self._exit_batch_mode(render=False)
        self._on_search(self._search_input.text())
        return moved

    def _move_selected_manuscripts(self):
        if not self._selected_manuscript_ids:
            return

        dialog = FolderPickerDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            moved = self._move_selected_to_folder(
                dialog.selected_folder_id()
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "移动失败",
                f"无法移动所选讲稿：\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "移动完成",
            f"已移动 {moved} 篇讲稿。",
        )

    def _selected_manuscripts(self) -> list[Manuscript]:
        return [
            manuscript
            for manuscript in self._manuscripts
            if manuscript.id in self._selected_manuscript_ids
        ]

    @staticmethod
    def _batch_delete_message(selected: list[Manuscript]) -> str:
        titles = [
            manuscript.title or "未命名稿件"
            for manuscript in selected
        ]
        preview = "\n".join(
            f"• {title}" for title in titles[:5]
        )
        remainder = len(titles) - 5
        if remainder > 0:
            preview += f"\n• 另有 {remainder} 篇"
        return (
            f"确定要永久删除选中的 {len(titles)} 篇讲稿吗？\n\n"
            f"{preview}\n\n此操作不可撤销。"
        )

    def _delete_selected_now(self) -> int:
        manuscript_ids = tuple(self._selected_manuscript_ids)
        if not manuscript_ids:
            return 0
        deleted = delete_manuscripts(manuscript_ids)
        self._exit_batch_mode(render=False)
        self._on_search(self._search_input.text())
        return deleted

    def _delete_selected_manuscripts(self):
        selected = self._selected_manuscripts()
        if not selected:
            return

        reply = QMessageBox.question(
            self,
            "确认批量删除",
            self._batch_delete_message(selected),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = self._delete_selected_now()
        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                f"无法删除所选讲稿：\n{error}",
            )
            return

        QMessageBox.information(
            self,
            "删除完成",
            f"已删除 {deleted} 篇讲稿。",
        )

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

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Escape
            and self._batch_mode
        ):
            self._exit_batch_mode()
            event.accept()
            return
        super().keyPressEvent(event)

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
                        html_content = clean_imported_html(html_content)
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
                    html_content = clean_imported_html(html_content)
                    html_content = compress_images_in_html(html_content)
                    create_manuscript(title, html_content, folder_id=self._current_folder_id)
                    imported += 1
            except Exception:
                pass

        if imported > 0:
            QMessageBox.information(self, "导入完成", f"已导入 {imported} 个文件。")
