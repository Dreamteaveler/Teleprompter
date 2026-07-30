import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from app import database
from app.pages.home_page import FolderCard, HomePage, ManuscriptCard


class _TopLevelReparentRecorder(QObject):
    """Records dynamically created widgets which Qt has to reparent."""

    def __init__(self, tracked_types: tuple[type[QWidget], ...]):
        super().__init__()
        self._tracked_types = tracked_types
        self.reparented_widget_types: list[str] = []

    def eventFilter(self, watched, event):
        if (
            isinstance(watched, self._tracked_types)
            and event.type() == QEvent.Type.ParentChange
        ):
            self.reparented_widget_types.append(type(watched).__name__)
        return False


class _PrompterPageStub(QWidget):
    """Avoids QWebEngine startup while preserving MainWindow's widget contract."""

    back_to_home = pyqtSignal()
    completed = pyqtSignal()
    edit_current_manuscript = pyqtSignal(int, float)


class WindowParentingTest(unittest.TestCase):
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
        self._widgets: list[QWidget] = []

        data_dir = Path(self._temp_dir.name) / "data"
        database.DATA_DIR = str(data_dir)
        database.DB_PATH = str(data_dir / "teleprompter.db")
        database.DOCS_DIR = str(data_dir / "documents")
        database._local.conn = None
        database.init_database()

    def tearDown(self):
        for widget in reversed(self._widgets):
            widget.hide()
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

    def _record_top_level_reparents(self, callback, tracked_types):
        recorder = _TopLevelReparentRecorder(tracked_types)
        self._app.installEventFilter(recorder)
        try:
            callback()
            self._app.processEvents()
            return recorder.reparented_widget_types
        finally:
            self._app.removeEventFilter(recorder)

    def _create_page_with_content(self):
        database.create_folder("项目")
        database.create_manuscript("演讲稿", "<p>正文</p>")
        page = HomePage()
        self._widgets.append(page)
        page.show()
        self._app.processEvents()
        return page

    @staticmethod
    def _main_window_class_with_prompter_stub():
        prompter_module_name = "app.pages.prompter_page"
        main_window_module_name = "app.pages.main_window"
        previous_prompter_module = sys.modules.get(prompter_module_name)
        previous_main_window_module = sys.modules.pop(main_window_module_name, None)
        stub_module = types.ModuleType(prompter_module_name)
        stub_module.PrompterPage = _PrompterPageStub
        sys.modules[prompter_module_name] = stub_module
        try:
            return importlib.import_module(main_window_module_name).MainWindow
        finally:
            sys.modules.pop(main_window_module_name, None)
            if previous_main_window_module is not None:
                sys.modules[main_window_module_name] = previous_main_window_module
            if previous_prompter_module is None:
                sys.modules.pop(prompter_module_name, None)
            else:
                sys.modules[prompter_module_name] = previous_prompter_module

    def test_refresh_never_reparents_dynamic_cards_from_top_level(self):
        page = self._create_page_with_content()

        reparented = self._record_top_level_reparents(
            page.refresh,
            (FolderCard, ManuscriptCard),
        )

        self.assertEqual(reparented, [])

    def test_ensure_prompter_constructs_page_as_stack_child(self):
        main_window_class = self._main_window_class_with_prompter_stub()
        window = main_window_class()
        self._widgets.append(window)
        window.show()
        self._app.processEvents()

        reparented = self._record_top_level_reparents(
            window._ensure_prompter,
            (_PrompterPageStub,),
        )

        self.assertEqual(reparented, [])


if __name__ == "__main__":
    unittest.main()
