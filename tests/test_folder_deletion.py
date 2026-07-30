import tempfile
import unittest
from pathlib import Path

from app import database


class FolderDeletionTest(unittest.TestCase):
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

    def test_delete_folder_removes_nested_folders_and_their_manuscripts(self):
        parent = database.create_folder("待删除")
        child = database.create_folder("子文件夹", parent_id=parent.id)
        direct_manuscript = database.create_manuscript(
            "父文件夹稿件",
            "direct",
            folder_id=parent.id,
        )
        nested_manuscript = database.create_manuscript(
            "子文件夹稿件",
            "nested",
            folder_id=child.id,
        )

        survivor_folder = database.create_folder("保留")
        survivor_manuscript = database.create_manuscript(
            "保留稿件",
            "keep",
            folder_id=survivor_folder.id,
        )

        self.assertTrue(database.delete_folder(parent.id))

        self.assertIsNone(database.get_folder(parent.id))
        self.assertIsNone(database.get_folder(child.id))
        self.assertIsNone(database.get_manuscript(direct_manuscript.id))
        self.assertIsNone(database.get_manuscript(nested_manuscript.id))
        self.assertIsNotNone(database.get_folder(survivor_folder.id))
        self.assertIsNotNone(database.get_manuscript(survivor_manuscript.id))


if __name__ == "__main__":
    unittest.main()
