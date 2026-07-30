import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app import database
from app.widgets.batch_management import BatchActionBar, FolderPickerDialog


class BatchManagementWidgetsTest(unittest.TestCase):
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

        data_dir = Path(self._temp_dir.name) / "data"
        database.DATA_DIR = str(data_dir)
        database.DB_PATH = str(data_dir / "teleprompter.db")
        database.DOCS_DIR = str(data_dir / "documents")
        database._local.conn = None
        database.init_database()

    def tearDown(self):
        connection = getattr(database._local, "conn", None)
        if connection is not None:
            connection.close()

        database.DATA_DIR, database.DB_PATH, database.DOCS_DIR = self._original_paths
        database._local.conn = self._original_connection
        self._temp_dir.cleanup()

    def test_action_bar_reflects_selection_state(self):
        bar = BatchActionBar()

        bar.set_selection_state(selected_count=0, visible_count=3)

        self.assertFalse(bar.move_button.isEnabled())
        self.assertFalse(bar.delete_button.isEnabled())
        self.assertEqual(bar.count_label.text(), "已选 0 项")
        self.assertEqual(
            bar.select_all_checkbox.checkState(),
            Qt.CheckState.Unchecked,
        )

        bar.set_selection_state(selected_count=3, visible_count=3)

        self.assertTrue(bar.move_button.isEnabled())
        self.assertTrue(bar.delete_button.isEnabled())
        self.assertEqual(bar.count_label.text(), "已选 3 项")
        self.assertEqual(
            bar.select_all_checkbox.checkState(),
            Qt.CheckState.Checked,
        )

    def test_action_bar_emits_select_all_intent(self):
        bar = BatchActionBar()
        choices = []
        bar.select_all_toggled.connect(choices.append)
        bar.set_selection_state(selected_count=0, visible_count=2)

        bar.select_all_checkbox.click()
        bar.select_all_checkbox.click()

        self.assertEqual(choices, [True, False])

    def test_action_bar_uses_organize_copy_and_context(self):
        bar = BatchActionBar()

        bar.set_context("全部稿件 › 项目", "演讲")
        bar.set_selection_state(selected_count=2, visible_count=3)

        self.assertEqual(bar.context_label.text(), "全部稿件 › 项目")
        self.assertEqual(bar.filter_label.text(), "筛选：“演讲”")
        self.assertTrue(bar.filter_label.isVisibleTo(bar))
        self.assertEqual(bar.count_label.text(), "已选 2 项")
        self.assertEqual(bar.move_button.text(), "移入文件夹")
        self.assertEqual(bar.exit_button.text(), "完成")

    def test_action_bar_hides_empty_filter_and_uses_compact_margins(self):
        bar = BatchActionBar()

        bar.set_context("全部稿件")
        bar.set_compact(True)

        self.assertFalse(bar.filter_label.isVisibleTo(bar))
        self.assertEqual(bar.layout().contentsMargins().left(), 24)

        bar.set_compact(False)

        self.assertEqual(bar.layout().contentsMargins().left(), 40)

    def test_action_bar_elides_long_context_with_full_tooltips(self):
        bar = BatchActionBar()
        path_text = (
            "全部稿件 › 第一层很长的文件夹 › "
            "第二层很长的文件夹 › 当前目录"
        )
        filter_text = "这是一个特别长的搜索关键词"

        bar.set_context(path_text, filter_text)

        self.assertIn("…", bar.context_label.text())
        self.assertEqual(bar.context_label.toolTip(), path_text)
        self.assertIn("…", bar.filter_label.text())
        self.assertEqual(
            bar.filter_label.toolTip(),
            f"筛选：“{filter_text}”",
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
        self.assertIsNotNone(database.get_folder(created.id))

    def test_folder_picker_rejects_empty_folder_name(self):
        dialog = FolderPickerDialog()

        with self.assertRaisesRegex(ValueError, "文件夹名称不能为空"):
            dialog.create_folder_under_selection("   ")


if __name__ == "__main__":
    unittest.main()
