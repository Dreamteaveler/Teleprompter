import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton

from app import database
from app.pages.home_page import HomePage


class HomePageNavigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._original_paths = (
            database.DATA_DIR,
            database.DB_PATH,
            database.DOCS_DIR,
        )
        self._original_connection = getattr(database._local, "conn", None)
        self._widgets = []

        data_dir = Path(self._temp_dir.name) / "data"
        database.DATA_DIR = str(data_dir)
        database.DB_PATH = str(data_dir / "teleprompter.db")
        database.DOCS_DIR = str(data_dir / "documents")
        database._local.conn = None
        database.init_database()

    def tearDown(self):
        for widget in self._widgets:
            widget.close()
            widget.deleteLater()
        self._app.processEvents()

        connection = getattr(database._local, "conn", None)
        if connection is not None:
            connection.close()

        database.DATA_DIR, database.DB_PATH, database.DOCS_DIR = (
            self._original_paths
        )
        database._local.conn = self._original_connection
        self._temp_dir.cleanup()

    def _create_page(self):
        page = HomePage()
        self._widgets.append(page)
        return page

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

        self.assertTrue(
            page._global_header.isAncestorOf(
                page._new_manuscript_button
            )
        )
        self.assertTrue(
            page._global_header.isAncestorOf(page._import_button)
        )
        for control in (
            page._search_input,
            page._new_folder_button,
            page._organize_button,
        ):
            self.assertTrue(page._normal_toolbar.isAncestorOf(control))

    def test_organize_mode_replaces_second_level_and_preserves_search(self):
        folder = database.create_folder("项目")
        database.create_manuscript(
            "演讲稿",
            "body",
            folder_id=folder.id,
        )
        page = self._create_page()
        page._on_folder_selected(folder.id)
        page._search_input.setText("演讲")

        page._enter_batch_mode()

        self.assertIs(
            page._toolbar_stack.currentWidget(),
            page._batch_bar,
        )
        self.assertEqual(
            page._batch_bar.context_label.text(),
            "全部稿件 › 项目",
        )
        self.assertEqual(
            page._batch_bar.filter_label.text(),
            "筛选：“演讲”",
        )
        self.assertEqual(page._search_input.text(), "演讲")

        page._exit_batch_mode()

        self.assertIs(
            page._toolbar_stack.currentWidget(),
            page._normal_toolbar,
        )
        self.assertEqual(page._search_input.text(), "演讲")

    def test_nested_folder_context_uses_text_only_clickable_breadcrumbs(self):
        parent = database.create_folder("项目")
        child = database.create_folder(
            "子文件夹",
            parent_id=parent.id,
        )
        page = self._create_page()

        page._on_folder_selected(child.id)

        self.assertEqual(
            page._current_path_text(),
            "全部稿件 › 项目 › 子文件夹",
        )
        texts = [
            button.text()
            for button in page._breadcrumb.findChildren(QPushButton)
        ]
        self.assertIn("全部稿件", texts)
        self.assertIn("项目", texts)
        self.assertIn("子文件夹", texts)
        self.assertTrue(
            all(
                "📂" not in text and "📁" not in text
                for text in texts
            )
        )


if __name__ == "__main__":
    unittest.main()
