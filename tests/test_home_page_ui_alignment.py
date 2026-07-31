import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton

from app import database
from app.pages.home_page import HomePage


TOOLBAR_HEIGHT = 36


class HomePageUiAlignmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        qss = Path("app/styles/theme.qss").read_text(encoding="utf-8")
        cls._app.setStyleSheet(qss)

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._original_paths = (
            database.DATA_DIR,
            database.DB_PATH,
            database.DOCS_DIR,
        )
        self._original_connection = getattr(database._local, "conn", None)

        data_dir = Path(self._temp_dir.name) / "data"
        database.DATA_DIR = str(data_dir)
        database.DB_PATH = str(data_dir / "teleprompter.db")
        database.DOCS_DIR = str(data_dir / "documents")
        database._local.conn = None
        database.init_database()
        self._widgets = []

    def tearDown(self):
        for widget in self._widgets:
            widget.close()
            widget.deleteLater()
        self._app.processEvents()

        connection = getattr(database._local, "conn", None)
        if connection is not None:
            connection.close()

        database.DATA_DIR, database.DB_PATH, database.DOCS_DIR = self._original_paths
        database._local.conn = self._original_connection
        self._temp_dir.cleanup()

    def _track(self, widget):
        self._widgets.append(widget)
        return widget

    def test_action_button_styles_share_toolbar_height(self):
        for name in ("ghostButton", "dangerButton", "accentButton"):
            button = QPushButton("测试")
            button.setObjectName(name)

            self.assertEqual(
                button.sizeHint().height(),
                TOOLBAR_HEIGHT,
                name,
            )

    def test_toolbar_controls_align_to_same_height(self):
        folder = database.create_folder("子目录")
        page = self._track(HomePage())
        page._on_folder_selected(folder.id)
        page.show()
        self._app.processEvents()

        breadcrumb_buttons = [
            button
            for button in page._breadcrumb.findChildren(QPushButton)
            if button.objectName() == "breadcrumbBtn"
        ]
        self.assertTrue(breadcrumb_buttons)

        heights = (
            [page._search_input.height()]
            + [page._new_folder_button.height()]
            + [page._organize_button.height()]
            + [button.height() for button in breadcrumb_buttons]
        )

        self.assertEqual(set(heights), {TOOLBAR_HEIGHT})

    def test_batch_bar_buttons_align_to_same_height(self):
        page = self._track(HomePage())
        page._enter_batch_mode()
        page.show()
        self._app.processEvents()

        heights = [
            page._batch_bar.move_button.height(),
            page._batch_bar.delete_button.height(),
            page._batch_bar.exit_button.height(),
        ]

        self.assertEqual(set(heights), {TOOLBAR_HEIGHT})


if __name__ == "__main__":
    unittest.main()
