"""Read-only content and layout checks for the frozen manuscript rendering.

Writes only this evidence directory; no scientific calculation or source edits.
"""
from __future__ import annotations

import base64
import difflib
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil

import fitz
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
MANUSCRIPT = HERE.parent.parent
ROOT = MANUSCRIPT.parent
RUNTIME = Path(r"D:\CodexRuntime\runs\r33_paper_render")
OLD = RUNTIME / "complete_v1_preview"
NEW = RUNTIME / "complete_v1_renderer_v2_preview_final"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normal(value):
    return "".join(value.split())


class HTMLContent(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.body = False
        self.skip_caption = 0
        self.text = []
        self.images = []
        self.math = self.tables = self.captions = self.scripts = 0
        self.external_dependencies = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "body":
            self.body = True
        if tag == "figcaption":
            self.skip_caption += 1
            self.captions += 1
        if tag == "math":
            self.math += 1
        if tag == "table":
            self.tables += 1
        if tag == "script":
            self.scripts += 1
        if tag == "img":
            self.images.append(attrs)
        if tag in ("script", "img", "iframe", "source", "link"):
            value = attrs.get("src", attrs.get("href", ""))
            if value and not value.startswith("data:"):
                self.external_dependencies.append({"tag": tag, "source": value})

    def handle_endtag(self, tag):
        if tag == "figcaption":
            self.skip_caption -= 1
        if tag == "body":
            self.body = False

    def handle_data(self, data):
        if self.body and not self.skip_caption:
            self.text.append(data)


def main():
    source = MANUSCRIPT / "drafts/complete_v1.md"
    assert sha(source) == "8c5a83cff08732ce8e548cd873faa4e55cede075c3340fe9799e9deae37d4fd3"
    old_renderer = MANUSCRIPT / "render_manuscript.py"
    renderer = MANUSCRIPT / "render_manuscript_v2.py"
    assert sha(old_renderer) == "c48735c16e1f8bc9da0e1ce9e4ead252de3fd6febe831ed1538a9ab35ed88000"
    old = json.loads((OLD / "complete_v1_render.json").read_text(encoding="utf-8"))
    new = json.loads((NEW / "complete_v1_render.json").read_text(encoding="utf-8"))
    assert old["source_sha256"] == new["source_sha256"] == sha(source)
    assert new["renderer_sha256"] == sha(renderer)
    assert new["missing_glyph_warnings"] == new["overfull_box_warnings"] == 0
    assert all(not page["outside_page_blocks"] for page in new["page_geometry"])

    old_html, new_html = HTMLContent(), HTMLContent()
    old_html.feed((OLD / "complete_v1.html").read_text(encoding="utf-8"))
    new_html.feed((NEW / "complete_v1.html").read_text(encoding="utf-8"))
    old_text, new_text = normal("".join(old_html.text)), normal("".join(new_html.text))
    assert old_text == new_text, "HTML body changed beyond removed automatic figure captions"
    assert old_html.captions == 4 and new_html.captions == 0
    assert old_html.math == new_html.math and old_html.tables == new_html.tables
    assert new_html.scripts == 0 and not new_html.external_dependencies
    assert len(old_html.images) == len(new_html.images) == 4
    images = []
    image_sources = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", source.read_text(encoding="utf-8"))
    assert len(image_sources) == 4
    for original, previous, current in zip(image_sources, old_html.images, new_html.images):
        assert previous == current
        embedded = base64.b64decode(current["src"].split(",", 1)[1])
        assert embedded == Path(original).read_bytes()
        images.append({"path": original, "sha256": sha(original), "embedded_exact_bytes": True})
    for i in range(1, 5):
        assert f"图{i}" in new_text

    old_tex = Path(old["tex"]).read_text(encoding="utf-8")
    new_tex = Path(new["tex"]).read_text(encoding="utf-8")
    def body(text):
        return text.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    old_body = re.sub(r"(?m)^\\(?:begin\{figure\}|end\{figure\}|centering|caption\{[^\n]+\})\n?", "", body(old_tex))
    new_body = body(new_tex).replace(r"\par\noindent\begin{minipage}{\linewidth}", "")
    new_body = new_body.replace(r"\noindent\pandocbounded", r"\pandocbounded")
    new_body = new_body.replace(r"\par\vspace{.35em}", "").replace(r"\end{minipage}\par", "")
    assert normal(old_body) == normal(new_body), "TeX body changed beyond figure layout wrappers"
    tables_old = re.findall(r"\\begin\{longtable\}.*?\\end\{longtable\}", old_tex, re.S)
    tables_new = re.findall(r"\\begin\{longtable\}.*?\\end\{longtable\}", new_tex, re.S)
    assert tables_old == tables_new and len(tables_new) == new_html.tables
    formulas_old = re.findall(r"\\\[.*?\\\]", old_tex, re.S)
    formulas_new = re.findall(r"\\\[.*?\\\]", new_tex, re.S)
    assert formulas_old == formulas_new
    assert new_tex.count(r"\begin{minipage}{\linewidth}") == 4
    assert r"\caption{" not in new_tex

    doc = fitz.open(new["pdf"])
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        assert not re.search(r"Figure\s+[1-4]:", text)
        body_lines = [line for line in text.splitlines() if line.strip() and line.strip() != str(i + 1)]
        pages.append({"page": i + 1, "body_lines": len(body_lines), "image_count": len(page.get_images()),
                      "text_characters": len(text)})
    image_pages = [row["page"] for row in pages if row["image_count"]]
    assert len(image_pages) == 4
    for i, page in enumerate(image_pages, start=1):
        assert f"图{i}" in doc[page - 1].get_text(), "Image separated from its handwritten caption"
    assert pages[-1]["body_lines"] > 3
    for suffix in ("render.json",):
        shutil.copyfile(NEW / ("complete_v1_" + suffix), HERE / ("final_" + suffix))
    shutil.copyfile(OLD / "complete_v1_render.json", HERE / "original_render.json")
    shutil.copyfile(RUNTIME / "complete_v1_renderer_v2_preview/complete_v1_render.json", HERE / "attempt1_render.json")
    shutil.copyfile(Path(new["compilation_logs"]) / "paper.log", HERE / "final_compile.log")
    shutil.copyfile(Path(new["tex"]), HERE / "final_compilation_source.tex")
    (HERE / "renderer_changes.diff").write_text("".join(difflib.unified_diff(
        old_renderer.read_text(encoding="utf-8").splitlines(keepends=True),
        renderer.read_text(encoding="utf-8").splitlines(keepends=True),
        fromfile="render_manuscript.py", tofile="render_manuscript_v2.py")), encoding="utf-8")

    preview_dir = Path(new["preview_directory"])
    thumb_w, thumb_h, top = 340, 481, 28
    contact = Image.new("RGB", (5 * (thumb_w + 12), 5 * (thumb_h + top + 12)), "#dfe4e9")
    draw = ImageDraw.Draw(contact)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 18)
    for i in range(len(doc)):
        page_image = Image.open(preview_dir / f"page_{i + 1:03}.png").convert("RGB")
        page_image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x, y = (i % 5) * (thumb_w + 12), (i // 5) * (thumb_h + top + 12)
        draw.text((x + 5, y + 3), f"Page {i + 1}", font=font, fill="#20242a")
        contact.paste(page_image, (x + 5, y + top))
    contact.save(HERE / "contact.png")
    visual_dir = HERE / "visual_checks"
    visual_dir.mkdir(exist_ok=True)
    for page in sorted(set(image_pages + [len(doc)])):
        shutil.copyfile(preview_dir / f"page_{page:03}.png", visual_dir / f"page_{page:03}.png")
    report = {"scope": "Manuscript typesetting preflight only; no science review or final delivery acceptance",
        "source_sha256_unchanged": sha(source), "original_renderer_sha256_unchanged": sha(old_renderer),
        "renderer_v2_sha256": sha(renderer), "html_sha256": sha(new["html"]), "pdf_sha256": sha(new["pdf"]),
        "source": str(source), "html": new["html"], "pdf": new["pdf"],
        "html_body_equal_except_removed_auto_captions": True, "html_body_normalized_sha256": digest(new_text),
        "tex_body_equal_except_figure_layout_wrappers": True, "tex_body_normalized_sha256": digest(normal(new_body)),
        "mathml_elements_preserved": new_html.math, "display_math_blocks_exact": len(formulas_new),
        "table_count_preserved": len(tables_new), "all_table_latex_exact": True,
        "old_automatic_caption_count": old_html.captions, "new_automatic_caption_count": new_html.captions,
        "handwritten_chinese_caption_count": 4, "all_images_embedded_exact": images,
        "html_remote_dependencies": [], "html_script_count": 0,
        "body_font_size_pt": 11, "margin_mm": 22, "line_spread": 1.25,
        "missing_glyph_warnings": 0, "overfull_box_warnings": 0, "outside_page_blocks": 0,
        "page_count": len(doc), "image_pages": image_pages, "last_page_body_lines": pages[-1]["body_lines"],
        "pages": pages, "visual_review": "PENDING human-visible tool inspection of contact and selected full pages"}
    (HERE / "render_checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("page_count", "image_pages", "last_page_body_lines", "mathml_elements_preserved", "display_math_blocks_exact", "table_count_preserved", "pdf_sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
