"""Validate saved report references and captured file hashes; no product writes."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

HERE = Path(__file__).resolve().parent
errors = []
pointers = 0
for name in ("findings.json", "capability-matrix.json"):
    doc = json.loads((HERE / name).read_text(encoding="utf-8"))
    for row in doc.get("findings", doc.get("capabilities", [])):
        for ref in row["code_refs"]:
            p = Path(ref["path"])
            if not p.is_file() or not 1 <= ref["line"] <= ref["end_line"] <= len(p.read_text(encoding="utf-8-sig").splitlines()):
                errors.append(["source_reference", row["id"], ref])
        for ref in row["runtime_refs"]:
            value = json.loads(Path(ref["path"]).read_text(encoding="utf-8"))
            try:
                for token in ref["json_pointer"].split("/")[1:]:
                    token = token.replace("~1", "/").replace("~0", "~")
                    value = value[int(token)] if isinstance(value, list) else value[token]
                pointers += 1
            except Exception as exc:
                errors.append(["runtime_reference", row["id"], ref, str(exc)])
md = (HERE / "ARCHITECTURE.md").read_text(encoding="utf-8")
links = 0
for target in re.findall(r"\]\((D:/[^)]+)\)", md):
    parts = target.rsplit(":", 1)
    p = Path(parts[0]) if len(parts) == 2 and parts[1].isdigit() else Path(target)
    if not p.is_file():
        errors.append(["markdown_missing", target])
    elif len(parts) == 2 and parts[1].isdigit() and int(parts[1]) > len(p.read_text(encoding="utf-8-sig").splitlines()):
        errors.append(["markdown_line", target])
    links += 1
for name in ("commands.json", "cli-commands.json"):
    doc = json.loads((HERE / "evidence" / name).read_text(encoding="utf-8"))
    for row in doc.get("smokes", doc.get("commands", [])):
        if row["returncode"] != 0:
            errors.append(["exit_code", row["case"], row["returncode"]])
        if "stdout_sha256" in row and hashlib.sha256(Path(row["stdout"]).read_bytes()).hexdigest() != row["stdout_sha256"]:
            errors.append(["stdout_hash", row["case"]])
status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=Path(r"D:\my_Works\Gears\gearbase-v020-work"), capture_output=True, text=True, check=True).stdout
changed = json.loads((HERE / "evidence/system.stdout.json").read_text(encoding="utf-8"))["results"]["summary"]["source_changed_values"]
report = dict(runtime_pointers_validated=pointers, markdown_local_links_validated=links,
              errors=errors, git_status=status, product_tree_clean=status == "",
              source_change_numeric_count=len(changed),
              capture_normalization="stdout_text_utf8_sha256 hashes normalized subprocess text; stdout_sha256 hashes saved file bytes, which may contain CRLF on Windows.")
(HERE / "evidence/artifact-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
raise SystemExit(0 if not errors and status == "" else 1)
