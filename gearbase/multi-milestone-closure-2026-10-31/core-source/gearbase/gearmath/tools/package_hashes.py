"""重新生成 MANIFEST.json 中的 sha256 与 PACKAGE-CONTENTS.sha256（零依赖）。

用法（在包根目录）：
    python3 -m gearmath.tools.package_hashes           # 重写两个文件
    python3 -m gearmath.tools.package_hashes --check   # 只核对，不一致则退出 2

MANIFEST 只更新已登记行的 sha256（origin/role 不改）；PACKAGE-CONTENTS 覆盖除自身、__pycache__、.pyc 及分包 2–5 目录（bank/ vendor/ archive/）外的全部核心文件，
行格式 `<sha256>  gearbase/<相对路径>`，按路径排序。"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTENTS = "PACKAGE-CONTENTS.sha256"
OTHER_PACKS = {"bank", "vendor", "archive"}   # 分包 2–5 的顶层目录，合并解压时不计入核心清单
RUNTIME_DIRS = {".git", ".pytest_cache", ".m32-ci"}


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def update_manifest(root=ROOT, write=True):
    path = root / "MANIFEST.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    stale = []
    for row in m["data"] + m["legacy"]:
        h = _sha(root / row["path"])
        if row["sha256"] != h:
            stale.append(row["path"])
            row["sha256"] = h
    if write and stale:
        path.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return stale


def contents_text(root=ROOT):
    rows = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if not p.is_file() or rel.parts[0] in OTHER_PACKS | RUNTIME_DIRS or rel.parts[:2] == ("output", "m32-ci") or "__pycache__" in rel.parts or p.suffix == ".pyc" or rel.as_posix() == CONTENTS:
            continue
        rows.append((rel.as_posix(), _sha(p)))
    return "".join(f"{h}  gearbase/{r}\n" for r, h in sorted(rows))


def main(argv):
    check = "--check" in argv
    stale = update_manifest(write=not check)
    text = contents_text()
    cur = (ROOT / CONTENTS).read_text(encoding="utf-8") if (ROOT / CONTENTS).exists() else ""
    if check:
        bad = bool(stale) or text != cur
        print("不一致：" + ("MANIFEST " + ",".join(stale) if stale else "") + (" PACKAGE-CONTENTS" if text != cur else "") if bad else "一致")
        return 2 if bad else 0
    (ROOT / CONTENTS).write_text(contents_text(), encoding="utf-8")   # MANIFEST 可能刚改过，重算
    print(f"MANIFEST 更新 {len(stale)} 行；{CONTENTS} 已重写")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
