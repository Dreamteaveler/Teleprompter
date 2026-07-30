import re
import unittest
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app" / "templates" / "prompter.html"
FONT = ROOT / "app" / "fonts" / "NotoSansSC-Bold-CJK.woff2"


@dataclass(frozen=True)
class FontFace:
    family: str
    source: str
    weight: str
    unicode_ranges: tuple[tuple[int, int], ...]


def _declarations(block: str) -> dict[str, str]:
    return {
        name.lower(): value.strip()
        for name, value in re.findall(r"([\w-]+)\s*:\s*([^;{}]+);", block)
    }


def _unquote(value: str) -> str:
    return value.strip().strip("'\"")


def _parse_unicode_ranges(value: str) -> tuple[tuple[int, int], ...]:
    ranges = []
    for start, end in re.findall(
        r"U\+([0-9A-F]+)(?:-([0-9A-F]+))?",
        value,
        re.IGNORECASE,
    ):
        first = int(start, 16)
        ranges.append((first, int(end, 16) if end else first))
    return tuple(ranges)


class CssFontPolicy:
    def __init__(self, css: str):
        self.faces = {}
        for match in re.finditer(r"@font-face\s*\{([^{}]*)\}", css, re.DOTALL):
            declarations = _declarations(match.group(1))
            family = _unquote(declarations["font-family"])
            self.faces[family] = FontFace(
                family=family,
                source=declarations["src"],
                weight=declarations.get("font-weight", "auto"),
                unicode_ranges=_parse_unicode_ranges(
                    declarations.get("unicode-range", "U+0-10FFFF")
                ),
            )

        body_match = re.search(r"\bbody\s*\{([^{}]*)\}", css, re.DOTALL)
        if not body_match:
            raise AssertionError("prompter template has no body rule")
        self.body = _declarations(body_match.group(1))
        self.body_families = tuple(
            _unquote(family)
            for family in self.body["font-family"].split(",")
        )

        code_match = re.search(r"\.content\s+code\s*\{([^{}]*)\}", css, re.DOTALL)
        self.code = _declarations(code_match.group(1)) if code_match else {}

    def resolve(self, character: str) -> FontFace:
        codepoint = ord(character)
        for family in self.body_families:
            face = self.faces.get(family)
            if face is None:
                return FontFace(
                    family=family,
                    source=f"local('{family}')",
                    weight=self.body.get("font-weight", "400"),
                    unicode_ranges=((0, 0x10FFFF),),
                )
            if any(start <= codepoint <= end for start, end in face.unicode_ranges):
                return face
        raise AssertionError(f"no font resolves U+{codepoint:04X}")


class PrompterFontPolicyTest(unittest.TestCase):
    def test_embedded_font_is_static_bold_and_covers_only_cjk(self):
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
            for character in "中日あア한ᄀ，。":
                with self.subTest(character=character):
                    self.assertIn(ord(character), cmap)
            for character in "AéЖΩⅧ":
                with self.subTest(character=character):
                    self.assertNotIn(ord(character), cmap)
        finally:
            font.close()

    def test_composite_policy_routes_cjk_to_bold_and_other_text_to_times(self):
        policy = CssFontPolicy(TEMPLATE.read_text(encoding="utf-8"))

        for character in "中日あア한ᄀ，。":
            with self.subTest(character=character):
                face = policy.resolve(character)
                self.assertIn("url(", face.source)
                self.assertEqual(face.weight, "400")

        for character in "AéЖΩⅧ":
            with self.subTest(character=character):
                face = policy.resolve(character)
                self.assertTrue(
                    face.family == "Times New Roman"
                    or "Times New Roman" in face.source
                )

        self.assertIn(policy.code.get("font-family"), (None, "inherit"))


if __name__ == "__main__":
    unittest.main()
