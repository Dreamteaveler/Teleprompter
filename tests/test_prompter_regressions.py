import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import types
import unittest
from unittest.mock import Mock, patch
from lxml import etree, html
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent

from app.pages.prompter_page import PrompterPage
from app.pages.mirror_sync_mixin import MirrorSyncMixin
from app.pages.mirror_window import MirrorWindow
from app.shortcut_manager import ShortcutManager
from app.docx_importer import _convert_wr_element
from app.file_importer import _plain_to_html
from app.models import Manuscript


class SyncHost(MirrorSyncMixin):
    def __init__(self):
        self._is_mirror_open = True
        self._mirror_window = Mock()
        self._page_ready = True
        self._sync_pending = False
        self._sync_version = 0
        self._sync_timer = Mock()
        self._scroll_position = 0
        self._view = Mock()
        self.callbacks = []
        self._view.page().runJavaScript.side_effect = lambda script, cb: self.callbacks.append(cb)


class MirrorSyncRegressionTest(unittest.TestCase):
    def test_slow_callback_still_updates_without_unbounded_requests(self):
        host = SyncHost()
        for _ in range(5):
            host._tick_sync_mirror()
        self.assertEqual(len(host.callbacks), 1)
        host.callbacks[0]([400, 1000, 180, 300])
        host._mirror_window.sync_scroll_pct.assert_called_once_with(0.4)
        host._tick_sync_mirror()
        self.assertEqual(len(host.callbacks), 2)

    def test_stop_discards_old_callback_without_clearing_new_request(self):
        host = SyncHost()
        host._tick_sync_mirror()
        old = host.callbacks[0]
        host._stop_sync_timer()
        host._tick_sync_mirror()
        old([900, 1000, 0, 300])
        host._mirror_window.sync_scroll_pct.assert_not_called()
        self.assertTrue(host._sync_pending)
        host.callbacks[-1]([200, 1000, 100, 300])
        host._mirror_window.sync_scroll_pct.assert_called_once_with(0.2)

    def test_invalid_reply_releases_request(self):
        host = SyncHost()
        host._tick_sync_mirror()
        host.callbacks[0](None)
        host._tick_sync_mirror()
        self.assertEqual(len(host.callbacks), 2)

    def test_short_document_still_updates_guide(self):
        host = SyncHost()
        host._tick_sync_mirror()
        host.callbacks[0]([0, 0, 120, 300])
        host._mirror_window.set_reading_line.assert_called_once_with(120.0, 300.0)
        host._mirror_window.sync_scroll_pct.assert_called_once_with(0.0)

    def test_reply_after_close_does_not_touch_mirror(self):
        host = SyncHost()
        host._tick_sync_mirror()
        host._is_mirror_open = False
        host.callbacks[0]([400, 1000, 180, 300])
        host._mirror_window.sync_scroll_pct.assert_not_called()


class MirrorProbe:
    def __init__(self, flipped=False):
        self._vflip = flipped
        self._view = Mock()
        self._pending_scroll_y = 0.0
        self._pending_scroll_ratio = None
        self._pending_rl_y = 0.0
        self._page_ready = False
        self.set_reading_line = Mock()

    def __getattr__(self, name):
        return types.MethodType(getattr(MirrorWindow, name), self)


class PositionRegressionTest(unittest.TestCase):
    def test_reload_keeps_original_ratio_across_rapid_changes(self):
        probe = types.SimpleNamespace(
            _scroll_height=2000, _scroll_position=640, _view=Mock(),
            _content_version=0, _pending_scroll_ratio=None,
            _invalidate_sync_requests=Mock(), _build_html=lambda text: text,
        )
        probe._view.height.return_value = 720
        probe._current_scroll_ratio = lambda: PrompterPage._current_scroll_ratio(probe)
        PrompterPage._load_content(probe, '<p>A</p>', True)
        probe._scroll_position = 0
        PrompterPage._load_content(probe, '<p>A</p>', True)
        self.assertEqual(probe._pending_scroll_ratio, 0.5)

    def test_stale_restore_cannot_change_new_document(self):
        probe = Mock()
        probe._content_version = 2
        PrompterPage._on_layout_restored(probe, [900, 2000], 1)
        probe._on_scroll_restored.assert_not_called()

    def test_ratio_uses_scrollable_extent(self):
        host = types.SimpleNamespace(_scroll_height=2000, _scroll_position=640, _view=Mock())
        host._view.height.return_value = 720
        ratio = PrompterPage._current_scroll_ratio(host)
        self.assertAlmostEqual(ratio, 0.5)
        self.assertAlmostEqual(ratio * (2000 - 720), 640)

    def test_short_document_ratio_is_zero(self):
        host = types.SimpleNamespace(_scroll_height=600, _scroll_position=0, _view=Mock())
        host._view.height.return_value = 720
        self.assertEqual(PrompterPage._current_scroll_ratio(host), 0.0)

    def test_mirror_restores_percentage_after_loading(self):
        mirror = MirrorProbe()
        mirror.sync_scroll_pct(0.5)
        mirror._view.page().runJavaScript.assert_not_called()
        mirror._on_page_loaded(True)
        script = mirror._view.page().runJavaScript.call_args.args[0]
        self.assertIn('maxY*0.5', script)

    def test_flipped_mirror_restores_logical_percentage_once(self):
        mirror = MirrorProbe(flipped=True)
        mirror.sync_scroll_pct(0.25)
        mirror._on_page_loaded(True)
        script = mirror._view.page().runJavaScript.call_args.args[0]
        self.assertIn('maxY*0.75', script)

    def test_legacy_pixel_scroll_still_works(self):
        mirror = MirrorProbe()
        mirror.sync_scroll(640)
        mirror._on_page_loaded(True)
        self.assertIn('640', mirror._view.page().runJavaScript.call_args.args[0])

    def test_failed_mirror_load_does_not_apply_pending_scroll(self):
        mirror = MirrorProbe()
        mirror.sync_scroll_pct(0.5)
        mirror._on_page_loaded(False)
        mirror._view.page().runJavaScript.assert_not_called()


class RenderingRegressionTest(unittest.TestCase):
    def make_host(self):
        s = types.SimpleNamespace(_font_size=120, _line_spacing=1.2, _margin=5,
                                  _reading_line_opacity=0.8)
        s._extract_body = lambda t: PrompterPage._extract_body(s, t)
        s._plain_to_html = lambda t: PrompterPage._plain_to_html(s, t)
        s._fix_broken_emphasis = PrompterPage._fix_broken_emphasis
        return s

    def content(self, text):
        document = html.fromstring(PrompterPage._build_html(self.make_host(), text))
        return document.xpath('//div[@class="content"]')[0]

    def test_literal_tags_stay_text(self):
        text = '请读出 <speaker> 和 <b> & 这些符号'
        content = self.content(_plain_to_html(text))
        self.assertEqual(content.text_content(), text)
        self.assertEqual(content.xpath('.//speaker | .//b'), [])

    def test_entities_and_real_formatting_are_preserved(self):
        content = self.content('<p><strong>A &amp; B</strong> &lt; 5 &gt; 2</p>')
        self.assertEqual(content.text_content(), 'A & B < 5 > 2')
        self.assertEqual(len(content.xpath('.//strong')), 1)

    def test_formula_image_attribute_is_decoded_only_as_text(self):
        content = self.content('<p><img class="formula" data-latex="x&lt;y &amp; z&gt;0" /></p>')
        self.assertEqual(content.text_content(), '$x<y & z>0$')
        self.assertEqual(content.xpath('.//img'), [])

    def test_markdown_formula_does_not_become_a_tag(self):
        content = self.content('Formula: $a<b>c$')
        self.assertIn('$a<b>c$', content.text_content())


class ImportItalicRegressionTest(unittest.TestCase):
    def convert(self, value):
        attr = '' if value is None else f' w:val="{value}"'
        root = etree.fromstring(f'<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:rPr><w:i{attr}/></w:rPr><w:t>Hello 中文</w:t></w:r>'.encode())
        return ''.join(_convert_wr_element(root, {}))

    def test_explicit_false_is_not_italic(self):
        for value in ['0', 'false', 'off']:
            with self.subTest(value=value):
                self.assertEqual(self.convert(value), 'Hello 中文')

    def test_true_italics_remain_italic(self):
        for value in [None, '1', 'true', 'on']:
            with self.subTest(value=value):
                self.assertEqual(self.convert(value), '<em>Hello 中文</em>')


class ShortcutRegressionTest(unittest.TestCase):
    def setUp(self):
        self.window = object()
        self.obj = types.SimpleNamespace(window=lambda: self.window)
        self.manager = ShortcutManager(self.window)
        self.toggle = Mock()
        self.manager.set_shortcuts({Qt.Key.Key_Space: self.toggle, Qt.Key.Key_R: self.toggle, Qt.Key.Key_M: self.toggle})

    def key(self, key, mods=Qt.KeyboardModifier.NoModifier, repeat=False):
        return self.manager.eventFilter(self.obj, QKeyEvent(QEvent.Type.KeyPress, key, mods, '', repeat))

    def test_numpad_zero_only_and_no_auto_repeat(self):
        self.manager.set_keypad_toggle(self.toggle)
        self.assertFalse(self.key(Qt.Key.Key_0))
        self.assertTrue(self.key(Qt.Key.Key_0, Qt.KeyboardModifier.KeypadModifier))
        self.key(Qt.Key.Key_0, Qt.KeyboardModifier.KeypadModifier, repeat=True)
        self.toggle.assert_called_once()


    def test_editing_preserves_text_keys_including_numpad(self):
        self.manager.set_keypad_toggle(self.toggle)
        self.manager.set_text_editing(True)
        for key in [Qt.Key.Key_Space, Qt.Key.Key_R, Qt.Key.Key_M, Qt.Key.Key_Up]:
            self.assertFalse(self.key(key))
        self.assertFalse(self.key(Qt.Key.Key_0, Qt.KeyboardModifier.KeypadModifier))
        self.toggle.assert_not_called()

    def test_control_shortcuts_do_not_consume_editor_chords(self):
        self.assertFalse(self.key(Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier))
        self.toggle.assert_not_called()

    def test_space_still_toggles_in_playback(self):
        self.assertTrue(self.key(Qt.Key.Key_Space))
        self.toggle.assert_called_once()


class InlineProbe:
    def __init__(self):
        self._inline_editing = True
        self._inline_saving = False
        self._inline_actions = []
        self._manuscript = Manuscript(id=123, title='draft', content='old')
        self._view = Mock()
        self._shortcut_mgr = Mock()
        self._control_panel = Mock()
        self._pause = Mock()
        self._update_reading_line = Mock()
        self._sync_mirror_if_open = Mock()
        self._auto_resume = False

    def __getattr__(self, name):
        return types.MethodType(getattr(PrompterPage, name), self)


class InlineSaveRegressionTest(unittest.TestCase):
    def test_save_empty_content_before_leaving(self):
        probe = InlineProbe()
        after = Mock()
        with patch('app.database.update_manuscript', return_value=Manuscript(id=123)) as save:
            probe._finish_inline_edit(after)
            after.assert_not_called()
            callback = probe._view.page().runJavaScript.call_args.args[1]
            callback('')
            save.assert_called_once_with(123, 'draft', '')
        self.assertEqual(probe._manuscript.content, '')
        self.assertFalse(probe._inline_editing)
        after.assert_called_once()

    def test_save_failure_keeps_editing_and_does_not_continue(self):
        probe = InlineProbe()
        after = Mock()
        with patch('app.database.update_manuscript', side_effect=OSError('disk full')), patch('PyQt6.QtWidgets.QMessageBox.warning'):
            probe._finish_inline_edit(after)
            callback = probe._view.page().runJavaScript.call_args.args[1]
            callback('<p>new</p>')
        self.assertTrue(probe._inline_editing)
        self.assertFalse(probe._inline_saving)
        self.assertEqual(probe._manuscript.content, 'old')
        after.assert_not_called()

    def test_repeated_actions_share_one_save(self):
        probe = InlineProbe()
        first, second = Mock(), Mock()
        with patch('app.database.update_manuscript', return_value=Manuscript(id=123)) as save:
            probe._finish_inline_edit(first)
            probe._finish_inline_edit(second)
            probe._view.page().runJavaScript.assert_called_once()
            probe._view.page().runJavaScript.call_args.args[1]('<p>new</p>')
            save.assert_called_once()
        first.assert_called_once()
        second.assert_called_once()

if __name__ == '__main__':
    unittest.main()
