import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import database


class BatchManuscriptDatabaseTest(unittest.TestCase):
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

    def test_move_manuscripts_moves_only_changed_rows_to_nested_folder(self):
        source = database.create_folder("来源")
        target_parent = database.create_folder("目标父级")
        target = database.create_folder("目标子级", parent_id=target_parent.id)
        first = database.create_manuscript("一", "one", folder_id=source.id)
        second = database.create_manuscript("二", "two", folder_id=target.id)
        second_updated_at = second.updated_at

        changed = database.move_manuscripts(
            [first.id, second.id, first.id],
            target.id,
        )

        self.assertEqual(changed, 1)
        self.assertEqual(
            database.get_manuscript(first.id).parent_folder_id,
            target.id,
        )
        unchanged = database.get_manuscript(second.id)
        self.assertEqual(unchanged.parent_folder_id, target.id)
        self.assertEqual(unchanged.updated_at, second_updated_at)

    def test_move_manuscripts_to_root(self):
        folder = database.create_folder("来源")
        manuscript = database.create_manuscript(
            "稿件",
            "body",
            folder_id=folder.id,
        )

        changed = database.move_manuscripts([manuscript.id], None)

        self.assertEqual(changed, 1)
        self.assertIsNone(
            database.get_manuscript(manuscript.id).parent_folder_id
        )

    def test_move_manuscripts_rolls_back_for_invalid_target(self):
        source = database.create_folder("来源")
        first = database.create_manuscript("一", "one", folder_id=source.id)
        second = database.create_manuscript("二", "two", folder_id=source.id)

        with self.assertRaises(sqlite3.IntegrityError):
            database.move_manuscripts([first.id, second.id], 999_999)

        self.assertEqual(
            database.get_manuscript(first.id).parent_folder_id,
            source.id,
        )
        self.assertEqual(
            database.get_manuscript(second.id).parent_folder_id,
            source.id,
        )

    def test_delete_manuscripts_deletes_existing_selected_rows_only(self):
        first = database.create_manuscript("一", "one")
        second = database.create_manuscript("二", "two")
        survivor = database.create_manuscript("保留", "keep")

        deleted = database.delete_manuscripts(
            [first.id, second.id, first.id, 999_999]
        )

        self.assertEqual(deleted, 2)
        self.assertIsNone(database.get_manuscript(first.id))
        self.assertIsNone(database.get_manuscript(second.id))
        self.assertIsNotNone(database.get_manuscript(survivor.id))

    def test_empty_batches_do_not_modify_database(self):
        manuscript = database.create_manuscript("保留", "keep")

        self.assertEqual(database.move_manuscripts([], None), 0)
        self.assertEqual(database.delete_manuscripts([]), 0)
        self.assertIsNotNone(database.get_manuscript(manuscript.id))


if __name__ == "__main__":
    unittest.main()
