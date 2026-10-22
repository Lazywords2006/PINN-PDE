"""Render v2: preserve hand-written captions and avoid orphaned paragraph lines.

Use the separate r33-analysis environment. This does not touch research runs.
HTML uses native MathML, so equations do not require a remote JavaScript service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import fitz
import pypandoc

HERE = Path(__file__).resolve().parent
RUNTIME = Path(r"D:\CodexRuntime\runs\r33_paper_render")
XELATEX = Path(r"C:\Users\LazyM\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe")
FORMAT = "markdown+tex_math_single_backslash+tex_math_dollars+pipe_tables+fenced_code_blocks-implicit_figures"

CSS = """
body{max-width:1020px;margin:2.5rem auto;padding:0 1.5rem;color:#20242a;
font:17px/1.85 'Noto Serif CJK SC','Source Han Serif SC','SimSun',serif}
h1,h2,h3{line-height:1.45;color:#152735}h1{font-size:1.85rem}h2{margin-top:2.6rem}
p{text-align:justify;orphans:3;widows:3}a{color:#245b87;text-decoration:none}a:hover{text-decoration:underline}
table{border-collapse:collapse;width:100%;font-size:.83rem;display:block;overflow-x:auto}
th,td{padding:.45rem .65rem;border-bottom:1px solid #d6dce1;text-align:left}
th{border-top:2px solid #52616b;background:#f3f5f6}img{max-width:100%;height:auto}
pre{background:#f4f6f7;padding:1rem;overflow:auto}code{font-size:.87em}
blockquote{border-left:3px solid #879cab;margin:1.3rem 0;padding:.3rem 1.2rem;color:#4e5961}
math[display=block]{overflow:auto;margin:1.2rem 0}.status{border:1px solid #b9c4cc;padding:.8rem 1rem}
@media print{body{max-width:none;margin:0;font-size:10.5pt}h2,h3{break-after:avoid}
table{display:table;font-size:8pt}tr,img{break-inside:avoid}a{color:inherit}}
"""

TEX_TEMPLATE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[margin=22mm]{geometry}
\usepackage{fontspec}
\setmainfont{SimSun}[AutoFakeBold=2,AutoFakeSlant=.15]
\setsansfont{Microsoft YaHei}
\setmonofont{Consolas}
\XeTeXlinebreaklocale "zh"
\XeTeXlinebreakskip=0pt plus 1pt
\usepackage{amsmath,amssymb,graphicx,longtable,booktabs,array,calc,xcolor,etoolbox}
\newcounter{none}
\AtBeginEnvironment{longtable}{\fontsize{8}{11}\selectfont\setlength{\tabcolsep}{3pt}}
\usepackage[unicode=true,colorlinks=true,linkcolor=black,urlcolor=blue]{hyperref}
\linespread{1.25}
\setlength{\parindent}{2em}
\setlength{\parskip}{.35em}
\setlength{\emergencystretch}{3em}
\clubpenalty=10000
\widowpenalty=10000
\displaywidowpenalty=10000
\raggedbottom
\setcounter{secnumdepth}{-1}
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\providecommand{\passthrough}[1]{#1}
\newcommand{\pandocbounded}[1]{\begingroup\setbox0=\hbox{#1}%
\ifdim\wd0>\linewidth\resizebox{\linewidth}{!}{\usebox0}\else\usebox0\fi\endgroup}
\begin{document}
\noindent\small\textsf{$status$}\normalsize\par\medskip
$body$
\end{document}
"""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(source, output, label, pdf):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not Path(r"D:\CodexRuntime").is_dir():
        raise RuntimeError("D:\\CodexRuntime 不可用，不回退 C:。")
    output.mkdir(parents=True, exist_ok=True)
    source_hash = sha(source)
    renderer_hash = sha(__file__)
    work = RUNTIME / (source.stem + "_" + source_hash[:12] + "_renderer_v2_" + renderer_hash[:12])
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=r"D:\CodexRuntime\temp", TMP=r"D:\CodexRuntime\temp")
    pandoc = pypandoc.get_pandoc_path()
    css = work / "paper.css"
    css.write_text(CSS, encoding="utf-8")
    banner = work / "banner.html"
    import html
    banner.write_text('<p class="status">' + html.escape(label) + '</p>', encoding="utf-8")
    common = [pandoc, str(source), "-f", FORMAT, "--standalone", "--wrap=none",
              "--resource-path", str(source.parent) + os.pathsep + str(HERE.parent),
              "--metadata", "title=R33 论文初稿", "--metadata", f"status={label}"]
    html_path = output / (source.stem + ".html")
    subprocess.run(common + ["--to=html5", "--mathml", "--embed-resources", "--css", str(css),
                            "--include-before-body", str(banner), "-o", str(html_path)],
                   cwd=source.parent, env=env, check=True)
    report = {"source": str(source), "source_sha256": source_hash, "label": label,
              "renderer": str(Path(__file__).resolve()), "renderer_sha256": renderer_hash,
              "markdown_reader_format": FORMAT,
              "caption_policy": "Original handwritten Chinese captions; implicit_figures disabled",
              "pdf_typography": "Original 11pt body, 22mm margins, 1.25 line spread; widow/club penalties 10000",
              "html": str(html_path), "html_sha256": sha(html_path),
              "html_math": "native MathML; no remote script", "pdf_requested": pdf,
              "visual_review": "pending; automated geometry checks do not replace inspection"}
    if pdf:
        template = work / "paper.tex.template"
        template.write_text(TEX_TEMPLATE, encoding="utf-8")
        tex = work / "paper.tex"
        subprocess.run(common + ["--to=latex", "--template", str(template), "--syntax-highlighting=none", "-o", str(tex)],
                       cwd=source.parent, env=env, check=True)
        tex_text = tex.read_text(encoding="utf-8")
        superscript_map = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾", "0123456789+-=()")
        superscripts = re.findall("[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾]+", tex_text)
        subscript_map = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₖ", "0123456789+-=()k")
        subscripts = re.findall("[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₖ]+", tex_text)
        report["tex_only_glyph_normalization"] = {
            "unicode_minus_to_math_minus": tex_text.count("\u2212"),
            "superscript_sequences_to_math": len(superscripts),
            "subscript_sequences_to_math": len(subscripts)}
        tex_text = tex_text.replace("\u2212", r"\ensuremath{-}")
        tex_text = re.sub("[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾]+",
                          lambda m: r"\ensuremath{^{" + m[0].translate(superscript_map) + "}}", tex_text)
        tex_text = re.sub("[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₖ]+",
                          lambda m: r"\ensuremath{_{" + m[0].translate(subscript_map) + "}}", tex_text)
        tex_text = re.sub(r"\\texttt\{([^{}]+)\}",
                          lambda m: r"\texttt{" + m[1].replace("/", r"/\allowbreak{}")
                          .replace("+", r"+\allowbreak{}") + "}", tex_text)
        tex_text = tex_text.replace(r"\_", r"\_\allowbreak{}")
        tex_text = tex_text.replace("hardic+layer", r"hardic+\allowbreak{}layer")
        # With implicit figures disabled, keep each image with its existing
        # Chinese caption. Only layout wrappers are added; caption text is kept.
        captioned_image = re.compile(r"(?m)^(\\pandocbounded\{\\includegraphics[^\n]+\})\n\n(图\d[^\n]+)")
        tex_text, captioned_image_count = captioned_image.subn(
            lambda m: "\\par\\noindent\\begin{minipage}{\\linewidth}\n"
                      "\\noindent" + m[1] + "\\par\\vspace{.35em}\n"
                      + m[2] + "\n\\end{minipage}\\par", tex_text)
        report["handwritten_caption_blocks_kept_together"] = captioned_image_count
        tex.write_text(tex_text, encoding="utf-8")
        for attempt in (1, 2):
            with (work / f"xelatex_{attempt}.stdout.log").open("w", encoding="utf-8") as log:
                result = subprocess.run([str(XELATEX), "-disable-installer", "-no-shell-escape",
                                         "-interaction=nonstopmode", "-halt-on-error",
                                         "-output-directory=" + str(work), str(tex)],
                                        cwd=source.parent, env=env, stdout=log,
                                        stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f"PDF 编译失败，保留源与日志：{work}")
        compile_log = (work / "paper.log").read_text(encoding="utf-8", errors="replace")
        report["missing_glyph_warnings"] = compile_log.count("Missing character:")
        report["overfull_box_warnings"] = compile_log.count("Overfull")
        if report["missing_glyph_warnings"]:
            raise RuntimeError(f"PDF 仍有缺失字形，不能交付：{work}")
        pdf_path = output / (source.stem + ".pdf")
        shutil.copyfile(work / "paper.pdf", pdf_path)
        doc = fitz.open(pdf_path)
        report.update(pdf=str(pdf_path), pdf_sha256=sha(pdf_path), pages=len(doc),
                      extracted_text_characters=sum(len(p.get_text()) for p in doc),
                      tex=str(tex), compilation_logs=str(work))
        checks = []
        for page_index, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            outside = []
            for block in blocks:
                rect = fitz.Rect(block["bbox"])
                if rect.x0 < 0 or rect.y0 < 0 or rect.x1 > page.rect.width + 1 or rect.y1 > page.rect.height + 1:
                    outside.append(list(rect))
            checks.append({"page": page_index + 1, "outside_page_blocks": outside})
        report["page_geometry"] = checks
        preview = work / "previews"
        preview.mkdir(exist_ok=True)
        for i in range(len(doc)):
            doc[i].get_pixmap(matrix=fitz.Matrix(1.3, 1.3)).save(preview / f"page_{i + 1:03}.png")
        report["preview_directory"] = str(preview)
    if sha(source) != source_hash:
        raise RuntimeError("原稿在排版过程中发生变化，请以冻结原稿重新渲染。")
    (output / (source.stem + "_render.json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--label", required=True)
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    render(args.source, args.output, args.label, args.pdf)
