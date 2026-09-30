import os
from pathlib import Path
import unittest
from unittest.mock import patch

from build_exe import build_environment


class BuildEnvironmentTests(unittest.TestCase):
    def test_foreign_dll_search_paths_are_not_inherited(self):
        with patch.dict(os.environ, {'PATH': r'C:\unrelated\poppler;C:\unrelated\Qt', 'KEEP_SETTING': 'yes'}):
            env = build_environment()
            self.assertNotIn('unrelated', env['PATH'])
            self.assertEqual(env['KEEP_SETTING'], 'yes')
            self.assertIn('unrelated', os.environ['PATH'])
            self.assertTrue(any(Path(p).name.lower() == 'system32' for p in env['PATH'].split(os.pathsep)))
