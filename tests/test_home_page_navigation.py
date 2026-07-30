import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

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


if __name__ == "__main__":
    unittest.main()
