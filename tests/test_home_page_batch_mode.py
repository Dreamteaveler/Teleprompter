import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app import database
from app.pages.home_page import HomePage, ManuscriptCard


class HomePageBatchModeTest(unittest.TestCase):
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

        database.DATA_DIR, database.DB_PATH, database.DOCS_DIR = self._original_paths
        database._local.conn = self._original_connection
        self._temp_dir.cleanup()

    def _track(self, widget):
        self._widgets.append(widget)
        return widget

    def _create_page(self):
        return self._track(HomePage())

    def test_card_checkbox_toggles_selection_without_playing(self):
        manuscript = database.create_manuscript("稿件", "body")
        card = self._track(
            ManuscriptCard(
                manuscript,
                batch_mode=True,
                selected=False,
            )
        )
        selected = []
        played = []
        card.selection_toggled.connect(
            lambda manuscript_id, value: selected.append(
                (manuscript_id, value)
            )
        )
        card.play_clicked.connect(played.append)

        card.selection_checkbox.click()

        self.assertEqual(selected, [(manuscript.id, True)])
        self.assertEqual(played, [])
        self.assertTrue(card.is_selected())

    def test_clicking_card_body_toggles_selection_in_batch_mode(self):
        manuscript = database.create_manuscript("稿件", "body")
        card = self._track(
            ManuscriptCard(
                manuscript,
                batch_mode=True,
                selected=False,
            )
        )
        selected = []
        card.selection_toggled.connect(
            lambda manuscript_id, value: selected.append(
                (manuscript_id, value)
            )
        )
        card.show()
        self._app.processEvents()

        QTest.mouseClick(
            card,
            Qt.MouseButton.LeftButton,
            pos=QPoint(220, 160),
        )

        self.assertEqual(selected, [(manuscript.id, True)])
        self.assertTrue(card.is_selected())

    def test_clicking_card_body_still_plays_in_normal_mode(self):
        manuscript = database.create_manuscript("稿件", "body")
        card = self._track(ManuscriptCard(manuscript))
        played = []
        card.play_clicked.connect(played.append)
        card.show()
        self._app.processEvents()

        QTest.mouseClick(
            card,
            Qt.MouseButton.LeftButton,
            pos=QPoint(220, 160),
        )

        self.assertEqual(played, [manuscript.id])

    def test_home_page_select_all_uses_visible_manuscripts_only(self):
        first = database.create_manuscript("可见一", "one")
        second = database.create_manuscript("可见二", "two")
        folder = database.create_folder("文件夹")
        hidden = database.create_manuscript(
            "隐藏",
            "hidden",
            folder_id=folder.id,
        )
        page = self._create_page()

        page._enter_batch_mode()
        page._select_all_visible(True)

        self.assertEqual(
            page._selected_manuscript_ids,
            {first.id, second.id},
        )
        self.assertNotIn(hidden.id, page._selected_manuscript_ids)

    def test_search_change_exits_batch_mode_and_clears_selection(self):
        manuscript = database.create_manuscript("测试稿件", "body")
        page = self._create_page()
        page._enter_batch_mode()
        page._toggle_manuscript_selection(manuscript.id, True)

        page._search_input.setText("测试")

        self.assertFalse(page._batch_mode)
        self.assertEqual(page._selected_manuscript_ids, set())

    def test_folder_change_exits_batch_mode_and_clears_selection(self):
        manuscript = database.create_manuscript("测试稿件", "body")
        folder = database.create_folder("目标")
        page = self._create_page()
        page._enter_batch_mode()
        page._toggle_manuscript_selection(manuscript.id, True)

        page._on_folder_selected(folder.id)

        self.assertFalse(page._batch_mode)
        self.assertEqual(page._selected_manuscript_ids, set())
        self.assertEqual(page._current_folder_id, folder.id)

    def test_home_page_moves_selected_manuscripts_and_exits_batch_mode(self):
        first = database.create_manuscript("移动", "one")
        survivor = database.create_manuscript("保留", "two")
        target = database.create_folder("目标")
        page = self._create_page()
        page._enter_batch_mode()
        page._toggle_manuscript_selection(first.id, True)

        moved = page._move_selected_to_folder(target.id)

        self.assertEqual(moved, 1)
        self.assertEqual(
            database.get_manuscript(first.id).parent_folder_id,
            target.id,
        )
        self.assertIsNone(
            database.get_manuscript(survivor.id).parent_folder_id
        )
        self.assertFalse(page._batch_mode)
        self.assertEqual(page._selected_manuscript_ids, set())

    def test_home_page_deletes_selected_manuscripts_and_preserves_others(self):
        first = database.create_manuscript("删除", "one")
        survivor = database.create_manuscript("保留", "two")
        page = self._create_page()
        page._enter_batch_mode()
        page._toggle_manuscript_selection(first.id, True)

        deleted = page._delete_selected_now()

        self.assertEqual(deleted, 1)
        self.assertIsNone(database.get_manuscript(first.id))
        self.assertIsNotNone(database.get_manuscript(survivor.id))
        self.assertFalse(page._batch_mode)
        self.assertEqual(page._selected_manuscript_ids, set())


if __name__ == "__main__":
    unittest.main()
