"""Real QWebEngine integration check; run separately from the fast unit suite.

Uses an isolated temporary SQLite database. Optional --software selects software
rendering for CI; normal invocation keeps the machine's graphics configuration.
"""
import os
import sys
import time
import json
import tempfile
from pathlib import Path

if '--software' in sys.argv:
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--disable-gpu'
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from app import database
from app.pages.main_window import MainWindow
from app.pages.mirror_window import MirrorWindow


# WebEngine on Windows requires a nonempty argv, even for an isolated test app.
app = QApplication([sys.argv[0]])
temp = tempfile.TemporaryDirectory()
database.DATA_DIR = temp.name
database.DB_PATH = str(Path(temp.name) / 'test.db')
database.DOCS_DIR = str(Path(temp.name) / 'documents')
database.init_database()
window = MainWindow()
window.resize(1280, 720)
window._ensure_prompter()
p = window._prompter
window._stack.setCurrentWidget(p)
window.setWindowTitle('提词器回归验证（临时数据库）')
window.show()
p._inline_edit_warned = True
mirror = None
results = []


def wait(condition, label, timeout=15):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        app.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError('Timeout: ' + label)


def js(view, script):
    values = []
    view.page().runJavaScript(script, values.append)
    wait(lambda: bool(values), 'javascript')
    return values[0]


def settled():
    wait(lambda: p._page_ready and (not mirror or mirror._page_ready), 'both pages loaded')
    for view in [p._view] + ([mirror._view] if mirror else []):
        js(view, "window._testReady=false;Promise.all([document.fonts.ready,MathJax.startup.promise]).then(()=>{window._testReady=true;});")
        wait(lambda: js(view, 'window._testReady === true'), 'fonts and formulas')
    # Let scheduled mirror reload and progress sampling complete.
    until = time.monotonic() + 0.7
    wait(lambda: time.monotonic() > until, 'settle timers')
    wait(lambda: p._page_ready and (not mirror or mirror._page_ready), 'final pages loaded')


def ratio(view):
    return js(view, 'window.pageYOffset / Math.max(1,document.documentElement.scrollHeight-window.innerHeight)')


def mark(name, **data):
    results.append(dict(check=name, **data))
    print(json.dumps(results[-1], ensure_ascii=False), flush=True)


try:
    source = ''.join(f'<p>第{i}段 认真生活，努力前行。 Today we test reading and growth.</p>' for i in range(24))
    manuscript = database.create_manuscript('Integration', source)
    p.load_manuscript(manuscript)
    settled()
    js(p._view, 'window.scrollTo(0,(document.documentElement.scrollHeight-innerHeight)*0.4)')
    p._on_scroll_tick_position(js(p._view, 'scrollY'))
    p._on_scroll_height(js(p._view, 'document.documentElement.scrollHeight'))
    before = ratio(p._view)
    p._on_font_changed(p._font_size)
    settled()
    after = ratio(p._view)
    assert abs(before - after) < 0.002, (before, after)
    mark('same-layout position retained', before=before, after=after)

    mirror = MirrorWindow()
    mirror.play_pause_requested.connect(p._toggle_play)
    mirror.resize(960, 540)
    mirror.show()
    p._mirror_window = mirror
    p._is_mirror_open = True
    p._horizontal_flip = True
    p._vertical_flip = False
    mirror.set_flip(True, False)
    p._sync_mirror_content()
    p._start_sync_timer()
    settled()
    wait(lambda: abs(ratio(mirror._view) - ratio(p._view)) < 0.005, 'mirror follows')
    mark('different-width horizontal mirror', main=ratio(p._view), mirror=ratio(mirror._view), scale=mirror._view.zoomFactor())

    for value in [100, 130, 160, 120]:
        p._on_font_changed(value)
    settled()
    assert abs(ratio(p._view) - before) < 0.005
    wait(lambda: abs(ratio(mirror._view) - ratio(p._view)) < 0.005, 'rapid reload final sync')
    assert js(p._view, 'getComputedStyle(document.body).fontSize') == '120px'
    assert js(mirror._view, 'getComputedStyle(document.body).fontSize') == '120px'
    mark('rapid font changes preserve position and both sizes', main=ratio(p._view), mirror=ratio(mirror._view))

    p._on_vertical_flip_toggled(True)
    settled()
    wait(lambda: abs(ratio(mirror._view) + ratio(p._view) - 1) < 0.005, 'vertical mirror')
    mark('vertical mirror logical ratio', main=ratio(p._view), mirror=ratio(mirror._view))

    p._play()
    p._on_font_changed(125)
    settled()
    assert p._is_playing, 'playback did not resume'
    p._pause()
    mark('playing reload resumes')

    p._on_inline_edit()
    assert p._inline_editing and not p._is_playing
    js(p._view, "document.querySelector('.content').innerHTML='<p>edited r m 0 &lt;speaker&gt;</p>'")
    p._on_font_changed(130)
    wait(lambda: not p._inline_editing and not p._inline_saving, 'inline save')
    settled()
    assert 'edited r m 0' in database.get_manuscript(manuscript.id).content
    assert '<speaker>' in js(p._view, "document.querySelector('.content').textContent")
    mark('inline changes saved before parameter reload')

    p._on_inline_edit()
    js(p._view, "document.querySelector('.content').innerHTML=''")
    p._finish_inline_edit()
    wait(lambda: not p._inline_saving, 'empty save')
    assert database.get_manuscript(manuscript.id).content == ''
    mark('empty inline edit persisted')

    second = database.create_manuscript('Formula', '<p>Literal &lt;speaker&gt; &amp; text.</p><p>$x&lt;y$</p>')
    p.load_manuscript(second)
    settled()
    assert '<speaker>' in js(p._view, "document.querySelector('.content').textContent")
    assert js(p._view, "document.querySelectorAll('speaker').length") == 0
    assert js(p._view, "document.querySelectorAll('mjx-container').length") == 1
    mark('literal markup and MathJax preserved')
    print('PASS: all integration checks', flush=True)
    if '--interactive' in sys.argv:
        p.load_manuscript(database.create_manuscript('Keyboard test', source))
        settled()
        last_state = [None]
        def log_state():
            state = (p._is_playing, p._inline_editing, p._inline_saving)
            if state != last_state[0]:
                print('LIVE_STATE', state, flush=True)
                last_state[0] = state
        monitor = QTimer()
        monitor.timeout.connect(log_state)
        monitor.start(100)
        QTimer.singleShot(240000, app.quit)
        print('READY FOR KEYBOARD TEST', flush=True)
        app.exec()
finally:
    p._pause()
    p._stop_sync_timer()
    p._progress_timer.stop()
    p._resync_debounce_timer.stop()
    p._mirror_mode = False
    p._is_mirror_open = False
    if mirror:
        mirror.close()
    p._mirror_window = None
    p._control_panel.close()
    window.hide()
    app.processEvents()
    database._local.conn.close()
    database._local.conn = None
    temp.cleanup()
