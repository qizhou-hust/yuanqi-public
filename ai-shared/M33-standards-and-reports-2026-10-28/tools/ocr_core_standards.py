"""Produce page-indexed OCR for user-supplied scans. PDF images remain authoritative."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import fitz
import hashlib
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
SPECS = [
    ("ISO-TR-6336-30-2022-supplemented-reading-copy.pdf", "ISO-TR-6336-30-2022", 7, 63),
    ("ISO 6336-1-2019.pdf", "ISO-6336-1-2019", 9, 134),
    ("ISO 6336-2-2019.pdf", "ISO-6336-2-2019", 9, 37),
    ("ISO 6336-3-2019.pdf", "ISO-6336-3-2019-corrected-2020-11", 9, 55),
    ("ISO 6336-5-2016.pdf", "ISO-6336-5-2016", 7, 47),
    ("ISO 6336-6-2019.pdf", "ISO-6336-6-2019", 7, 37),
]


def page_text(source, index):
    with fitz.open(source) as doc:
        page = doc[index]
        text = page.get_text()
        if len(text.strip()) > 80:
            return index, text, "PDF_TEXT"
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        result = subprocess.run([TESSERACT, "stdin", "stdout", "-l", "eng", "--psm", "3"],
            input=pix.tobytes("png"), capture_output=True, check=True,
            env={**os.environ, "OMP_THREAD_LIMIT": "1"})
        return index, result.stdout.decode("utf-8").replace("\r", ""), "TESSERACT_OCR_UNVERIFIED"


def main():
    target = ROOT / "ai/standards-ocr"
    target.mkdir(parents=True, exist_ok=True)
    manifest = []
    for filename, label, first, last in SPECS:
        source = ROOT / "evidence/standards/core" / filename
        with fitz.open(source) as doc:
            count = len(doc)
        pages = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(page_text, source, i) for i in range(count)]
            for future in as_completed(futures):
                index, text, method = future.result()
                pages[index] = {"pdf_page": index + 1,
                    "printed_page": index + 2 - first if first <= index + 1 < first + last else None,
                    "method": method, "text": text}
                if len(pages) % 30 == 0:
                    print(f"{label}: {len(pages)}/{count}", flush=True)
        ordered = [pages[i] for i in range(count)]
        md = [f"# {label} — OCR reading aid", "",
              "WARNING: OCR has not been proofread. Symbols, equations, decimal points and table columns may be wrong. Check the original PDF page image before using a number or formula. This text does not change the source's copyright or licence.", "",
              f"Source: ../../evidence/standards/core/{filename}",
              f"Source SHA-256: {hashlib.sha256(source.read_bytes()).hexdigest()}", ""]
        for row in ordered:
            md += [f"## PDF page {row['pdf_page']} | printed page {row['printed_page']} | {row['method']}", "", row["text"], ""]
        (target / (label + ".md")).write_text("\n".join(md), encoding="utf-8")
        (target / (label + ".json")).write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append({"standard": label, "source": source.relative_to(ROOT).as_posix(),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "pdf_pages": count,
            "markdown": f"ai/standards-ocr/{label}.md", "json": f"ai/standards-ocr/{label}.json",
            "status": "OCR_UNVERIFIED_USE_PDF_IMAGES_FOR_FORMULAS"})
        (ROOT / "ai/ocr-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{label}: complete, {count} pages", flush=True)


if __name__ == "__main__":
    main()
