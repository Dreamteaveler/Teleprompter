import tempfile
import unittest
from pathlib import Path

from app import database


class FolderBatchDatabaseTest(unittest.TestCase):
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

    def test_get_folder_subtree_ids_includes_nested_descendants(self):
        parent = database.create_folder("父")
        child = database.create_folder("子", parent_id=parent.id)
        grandchild = database.create_folder("孙", parent_id=child.id)
        other = database.create_folder("无关")

        subtree = database.get_folder_subtree_ids([parent.id])

        self.assertEqual(subtree, {parent.id, child.id, grandchild.id})
        self.assertNotIn(other.id, subtree)

    def test_move_folders_moves_to_target_and_root(self):
        source = database.create_folder("来源")
        target = database.create_folder("目标")
        other = database.create_folder("其他")

        changed = database.move_folders(
            [source.id, other.id, source.id],
            target.id,
        )

        self.assertEqual(changed, 2)
        self.assertEqual(
            database.get_folder(source.id).parent_folder_id,
            target.id,
        )
        self.assertEqual(
            database.get_folder(other.id).parent_folder_id,
            target.id,
        )

        root_changed = database.move_folders([source.id], None)
        self.assertEqual(root_changed, 1)
        self.assertIsNone(database.get_folder(source.id).parent_folder_id)

    def test_move_folders_skips_folders_already_at_target(self):
        target = database.create_folder("目标")
        child = database.create_folder("子", parent_id=target.id)
        before = child.updated_at

        changed = database.move_folders([child.id], target.id)

        self.assertEqual(changed, 0)
        self.assertEqual(database.get_folder(child.id).updated_at, before)

    def test_move_folders_rejects_moving_into_own_descendant(self):
        parent = database.create_folder("父")
        child = database.create_folder("子", parent_id=parent.id)
        grandchild = database.create_folder("孙", parent_id=child.id)

        with self.assertRaises(ValueError):
            database.move_folders([parent.id], grandchild.id)

        self.assertIsNone(database.get_folder(parent.id).parent_folder_id)
        self.assertEqual(
            database.get_folder(child.id).parent_folder_id,
            parent.id,
        )

    def test_delete_folders_removes_tree_and_keeps_unrelated(self):
        parent = database.create_folder("待删父")
        child = database.create_folder("待删子", parent_id=parent.id)
        parent_manuscript = database.create_manuscript(
            "父内稿件",
            "a",
            folder_id=parent.id,
        )
        child_manuscript = database.create_manuscript(
            "子内稿件",
            "b",
            folder_id=child.id,
        )
        survivor = database.create_folder("保留")
        survivor_manuscript = database.create_manuscript(
            "保留稿件",
            "c",
            folder_id=survivor.id,
        )

        deleted = database.delete_folders([parent.id, parent.id, 999_999])

        self.assertEqual(deleted, 1)
        self.assertIsNone(database.get_folder(parent.id))
        self.assertIsNone(database.get_folder(child.id))
        self.assertIsNone(database.get_manuscript(parent_manuscript.id))
        self.assertIsNone(database.get_manuscript(child_manuscript.id))
        self.assertIsNotNone(database.get_folder(survivor.id))
        self.assertIsNotNone(database.get_manuscript(survivor_manuscript.id))

    def test_delete_folders_empty_returns_zero(self):
        folder = database.create_folder("保留")

        self.assertEqual(database.delete_folders([]), 0)
        self.assertIsNotNone(database.get_folder(folder.id))


if __name__ == "__main__":
    unittest.main()
