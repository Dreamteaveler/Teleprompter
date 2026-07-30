# Prompter Font Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every prompter manuscript render Chinese, Japanese, and Korean text with an embedded real Bold gothic font while all non-CJK prose uses Times New Roman.

**Architecture:** Keep importers format-focused and enforce typography once in the shared `PrompterPage` HTML template used by the main and mirror views. Replace the incomplete Thin variable subset with a static Noto Sans CJK SC Bold subset whose cmap and CSS `unicode-range` both cover Chinese, Japanese, and Korean.

**Tech Stack:** Python 3.12, `unittest`, fontTools, WOFF2, CSS `@font-face`, PyQt6 WebEngine.

## Global Constraints

- Chinese, Japanese, and Korean characters use an embedded physical weight-700 gothic font.
- English, French, Russian, Greek, Roman numerals, and other non-CJK prose use Times New Roman at the document's requested weight.
- Button import, single-file drop, batch drop, folder drop, existing manuscripts, and the mirror view share one rendering policy.
- MathJax keeps its dedicated mathematical fonts.
- Back up every modified important file under `Backup/` as `<filename>_yyyy-MM-dd_HHmmss.bak`, retaining at most 30 backups per source file.
- Do not modify the manuscript database for this typography change.

---

### Task 1: Add a font-policy regression test

**Files:**
- Create: `tests/test_prompter_font_policy.py`
- Create: `requirements-dev.txt`
- Inspect: `app/templates/prompter.html`
- Inspect: `app/fonts/NotoSansSC-Bold-CJK.woff2`

**Interfaces:**
- Consumes: the checked-in prompter template and WOFF2 asset.
- Produces: an executable regression contract for font metadata, glyph coverage, and CSS routing.

- [x] **Step 1: Write the failing test**

```python
import re
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app" / "templates" / "prompter.html"
FONT = ROOT / "app" / "fonts" / "NotoSansSC-Bold-CJK.woff2"


def _unicode_ranges(css: str) -> list[tuple[int, int]]:
    block = re.search(
        r"@font-face\s*\{[^{}]*font-family:\s*'TPCJKBold'[^{}]*\}",
        css,
        re.DOTALL,
    )
    if not block:
        return []
    declaration = re.search(r"unicode-range:\s*([^;]+);", block.group(0))
    if not declaration:
        return []
    ranges = []
    for start, end in re.findall(
        r"U\+([0-9A-F]+)(?:-([0-9A-F]+))?",
        declaration.group(1),
        re.IGNORECASE,
    ):
        first = int(start, 16)
        ranges.append((first, int(end, 16) if end else first))
    return ranges


def _is_routed(ranges: list[tuple[int, int]], character: str) -> bool:
    codepoint = ord(character)
    return any(start <= codepoint <= end for start, end in ranges)


class PrompterFontPolicyTest(unittest.TestCase):
    def test_embedded_font_is_static_bold_and_covers_cjk(self):
        font = TTFont(FONT)
        try:
            cmap = {
                codepoint
                for table in font["cmap"].tables
                if table.isUnicode()
                for codepoint in table.cmap
            }
            self.assertNotIn("fvar", font)
            self.assertEqual(font["OS/2"].usWeightClass, 700)
            for character in "中あア한ᄀ":
                self.assertIn(ord(character), cmap)
        finally:
            font.close()

    def test_css_routes_only_cjk_to_embedded_bold(self):
        css = TEMPLATE.read_text(encoding="utf-8")
        ranges = _unicode_ranges(css)
        for character in "中あア한ᄀ，。":
            self.assertTrue(_is_routed(ranges, character), character)
        for character in "AéЖΩⅧ":
            self.assertFalse(_is_routed(ranges, character), character)
        self.assertRegex(
            css,
            r"font-family:\s*'TPCJKBold',\s*'Times New Roman',\s*serif;",
        )
```

- [x] **Step 2: Run the test to verify RED**

Run:

```text
C:\Users\17469\AppData\Local\Programs\Python\Python312\python.exe -m unittest tests.test_prompter_font_policy -v
```

Expected: both tests fail because the current asset is variable Thin, lacks Japanese/Korean glyphs, and the template has no `TPCJKBold` routing rule.

### Task 2: Build and license the real Bold pan-CJK subset

**Files:**
- Replace: `app/fonts/NotoSansSC-Bold-CJK.woff2`
- Create: `app/fonts/LICENSE-NOTO-CJK.txt`
- Modify: `app/paths.py`
- Modify: `Teleprompter.spec`
- Test: `tests/test_prompter_font_policy.py`

**Interfaces:**
- Consumes: official `NotoSansCJKsc-Bold.otf` from `notofonts/noto-cjk`.
- Produces: a static weight-700 WOFF2 containing the CJK, kana, and Hangul ranges used by the template.

- [x] **Step 1: Back up the current font and spec**

Create timestamped backups for `app/fonts/NotoSansSC-Bold-CJK.woff2` and `Teleprompter.spec`; prune only backups for each matching source name beyond the newest 30.

- [x] **Step 2: Subset the official static Bold source**

Use fontTools with this exact Unicode set:

```text
U+1100-11FF,U+2E80-2EFF,U+2F00-2FDF,U+2FF0-2FFF,U+3000-303F,
U+3040-309F,U+30A0-30FF,U+3100-312F,U+3130-318F,U+3190-319F,
U+31A0-31BF,U+31C0-31EF,U+31F0-31FF,U+3200-32FF,U+3300-33FF,
U+3400-4DBF,U+4E00-9FFF,U+A960-A97F,U+AC00-D7AF,U+D7B0-D7FF,
U+F900-FAFF,U+FE10-FE1F,U+FE30-FE4F,U+FF00-FFEF,
U+1B000-1B16F,U+1F200-1F2FF,U+20000-2FFFF,U+30000-3FFFF
```

Set WOFF2 flavor, preserve all layout features, and write atomically to `app/fonts/NotoSansSC-Bold-CJK.woff2`.

- [x] **Step 3: Add the upstream OFL license to packaging**

Store the upstream `Sans/LICENSE` verbatim as `app/fonts/LICENSE-NOTO-CJK.txt` and add it to `Teleprompter.spec` beside the WOFF2 data entry.

- [x] **Step 4: Run the metadata and coverage test**

Run the Task 1 test. Expected: the asset test passes; the CSS routing test remains RED.

### Task 3: Apply the shared CSS routing policy

**Files:**
- Modify: `app/templates/prompter.html`
- Test: `tests/test_prompter_font_policy.py`

**Interfaces:**
- Consumes: the static Bold WOFF2 from Task 2.
- Produces: a composite family where only CJK ranges use the embedded font and all other prose falls through to Times New Roman.

- [x] **Step 1: Back up the template**

Create a timestamped `Backup/prompter_yyyy-MM-dd_HHmmss.bak` and retain the newest 30 matching backups.

- [x] **Step 2: Replace the two existing font faces**

Use one face named `TPCJKBold`, map its physical Bold outlines into the CSS normal slot with `font-weight: 400`, and give it the exact CJK ranges from Task 2. Set the body family to:

```css
font-family: 'TPCJKBold', 'Times New Roman', serif;
font-weight: 400;
```

Remove the `TPLatin` face so Greek, Cyrillic, extended Latin, Roman numerals, and other non-CJK prose consistently fall through to Times New Roman. Make `.content code` inherit this same family; do not override MathJax descendants.

- [x] **Step 3: Run the regression test to verify GREEN**

Run the Task 1 test. Expected: 2 tests pass.

### Task 4: Verify the application artifact

**Files:**
- Verify: all changed files

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: fresh evidence that the font contract, Python source, and PyInstaller configuration remain valid.

- [x] **Step 1: Run all tests**

```text
C:\Users\17469\AppData\Local\Programs\Python\Python312\python.exe -m unittest discover -s tests -v
```

- [x] **Step 2: Compile Python sources**

```text
C:\Users\17469\AppData\Local\Programs\Python\Python312\python.exe -m compileall -q app main.py
```

- [x] **Step 3: Validate the PyInstaller spec**

Parse `Teleprompter.spec` with `ast.parse`, assert both font data files exist, and confirm no unresolved font placeholder remains after `PrompterPage._build_html()`.

- [x] **Step 4: Review Git diff and status**

Confirm only the plan, regression test, font asset/license, template, spec, and required timestamped backups changed; leave unrelated existing backups untouched.
