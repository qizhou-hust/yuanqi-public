"""Check scanned ISO page-number sequences without altering supplied PDFs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import fitz
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
ENV = {**os.environ, "OMP_THREAD_LIMIT": "1"}


def check_page(path, index):
    with fitz.open(path) as doc:
        page = doc[index]
        r = page.rect
        clip = fitz.Rect(r.width * .025, r.height * .90, r.width * .98, r.height * .99)
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip)
        r = subprocess.run([TESSERACT, "stdin", "stdout", "-l", "eng", "--psm", "6"],
                           input=pix.tobytes("png"), capture_output=True, env=ENV, check=True)
        text = r.stdout.decode("utf-8").strip()
        numbers = [int(x) for x in re.findall(r"(?<![\w.])\d{1,3}(?![\w.])", text) if 0 < int(x) <= len(doc)]
        return {"pdf_page": index + 1, "footer_ocr": text, "number_candidates": numbers}


def main():
    result = {}
    jobs = []
    for path in sorted((ROOT / "standards" / "core").glob("*.pdf")):
        with fitz.open(path) as doc:
            result[path.name] = {"pdf_pages": len(doc), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pages": []}
            jobs += [(path, i) for i in range(len(doc))]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(check_page, p, i): p.name for p, i in jobs}
        for future in as_completed(futures):
            result[futures[future]]["pages"].append(future.result())
    for name, item in result.items():
        item["pages"].sort(key=lambda x: x["pdf_page"])
        sequence = [p["number_candidates"][-1] for p in item["pages"] if p["number_candidates"]]
        maximum = max(sequence) if sequence else 0
        item["observed_max_page"] = maximum
        item["missing_number_candidates"] = sorted(set(range(1, maximum + 1)) - set(sequence))
        item["note"] = "OCR candidates require visual confirmation for every discontinuity; not an automatic completeness verdict."
        print(json.dumps({"name": name, "pdf_pages": item["pdf_pages"], "max": maximum, "missing": item["missing_number_candidates"]}), flush=True)
    (ROOT / "verification" / "standard-page-sequences.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
