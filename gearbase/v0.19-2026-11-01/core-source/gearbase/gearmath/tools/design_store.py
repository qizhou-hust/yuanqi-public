"""设计状态存储（零依赖）：内存模式与文件模式共用一个接口。

提交记录（commit record）不可变，按设计名形成链：
    {"schema", "design", "version"(从 1 起), "parent_version", "parent_sha256"(无父为 null),
     "sha256"(= spec 的规范 JSON sha256 = design_id), "model_sha256", "spec", "edit", "diff", "preview_token"}
M34 起提交单元是 gears.math-source/2 文档：记录可带 "source"（唯一可编辑真源，只含作者输入、证据、约束、选择器、版次）
与 "source_sha256"（= source 的规范 JSON sha256）；二者可选（旧记录没有），有则加载时逐条校验。派生量不进 source。
文件布局：<state_dir>/<设计名>/<version:08d>.json。写入 = 在同目录写临时文件（fsync）后用 os.link 发布到目标名
（目标已存在则失败，绝不覆盖），再删临时文件；因此记录要么完整出现、要么不出现，且同一版本号只可能被一个写者占用。
乐观锁：append 要求新记录 version == 当前头版本 + 1 且 parent_sha256 == 当前头 sha256，否则抛 VersionConflict。
加载时逐条校验链（版本连续、父哈希、spec 哈希），损坏抛 StateCorrupt，不静默修复。
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import re
import tempfile

SCHEMA = "gearbase.design-commit/1"
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_FILE = re.compile(r"^(\d{8})\.json$")


class VersionConflict(Exception):
    """并发写同一设计：版本号或父哈希与当前头不符。"""


class StateCorrupt(Exception):
    """磁盘上的记录链损坏（缺版本、父哈希不符、内容哈希不符、无法解析）。"""


class SourceOwnershipError(ValueError):
    """A source-owned design cannot accept an independent projection write."""


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def spec_sha256(spec):
    return hashlib.sha256(_canon(spec).encode("utf-8")).hexdigest()


def _check_name(name):
    if not isinstance(name, str) or not _NAME.match(name) or set(name) == {"."}:
        raise ValueError(f"设计名无效：{name!r}")


def check_source(source):
    """math-source/2 文档的结构与跨字段校验；不合格抛 ValueError（含逐项错误）。"""
    from ..gear import math_source as MS          # 延迟导入：存储层不在导入期依赖齿轮层
    errs = MS.validate(source)
    if errs:
        raise ValueError("；".join(f"{e['path']}：{e['message']}" for e in errs[:6]))


def make_record(name, head, spec, model_sha256, edit, diff, preview_token, source=None):
    rec = {"schema": SCHEMA, "design": name, "version": (head["version"] + 1) if head else 1,
           "parent_version": head["version"] if head else None, "parent_sha256": head["sha256"] if head else None,
           "sha256": spec_sha256(spec), "model_sha256": model_sha256, "spec": copy.deepcopy(spec),
           "edit": copy.deepcopy(edit), "diff": copy.deepcopy(diff), "preview_token": preview_token}
    if source is not None:
        check_source(source)
        rec["source"], rec["source_sha256"] = copy.deepcopy(source), spec_sha256(source)
    return rec


def _check_append(name, head, rec):
    want = (head["version"] + 1) if head else 1
    if rec["design"] != name or rec["version"] != want or rec["parent_sha256"] != (head["sha256"] if head else None):
        raise VersionConflict(f"设计 {name} 当前头版本 {head['version'] if head else 0}，记录要求父版本 {rec['parent_version']}")
    _check_ownership(head, rec)


def _check_ownership(head, rec):
    if head and 'source' in head and 'source' not in rec:
        raise SourceOwnershipError('source-owned design requires a math-source/2 revision')
    if 'source' not in rec:
        return  # Read/write compatibility for pre-migration chains only.
    check_source(rec['source'])
    if spec_sha256(rec['source']) != rec.get('source_sha256'):
        raise SourceOwnershipError('source hash mismatch')
    spec = rec.get('spec') or {}
    if spec.get('kind') in ('source_import', 'optimizer_revision'):
        if spec.get('source_sha256') != rec['source_sha256']:
            raise SourceOwnershipError('projection source hash mismatch')
    else:
        # Legacy edit is a translation into the one source, never an independent owner.
        from . import ai_tools as AI
        from ..gear import math_source as MS
        model, _, errors = AI._model(spec, trusted_projection=True)
        source_model = MS.build_model(rec['source'])
        def semantics(m):
            return ({k: (v.value, v.provenance) for k, v in m.inputs.items()},
                    m.selectors, m.editions)
        if errors or semantics(model) != semantics(source_model):
            raise SourceOwnershipError('legacy projection disagrees with math source')


class MemoryStore:
    mode = "in_memory"

    def __init__(self):
        self._chains = {}

    def head(self, name):
        _check_name(name)
        ch = self._chains.get(name)
        return copy.deepcopy(ch[-1]) if ch else None

    def history(self, name):
        _check_name(name)
        return copy.deepcopy(self._chains.get(name, []))

    def append(self, name, rec):
        _check_name(name)
        ch = self._chains.setdefault(name, [])
        _check_append(name, ch[-1] if ch else None, rec)
        ch.append(copy.deepcopy(rec))

    def names(self):
        return sorted(self._chains)


class FileStore:
    mode = "file"

    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, name):
        _check_name(name)
        return self.root / name

    def history(self, name):
        d = self._dir(name)
        if not d.is_dir():
            return []
        files = sorted(p for p in d.iterdir() if _FILE.match(p.name))
        out, prev = [], None
        for i, p in enumerate(files, 1):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                raise StateCorrupt(f"{p.name}：无法解析：{e}") from e
            if (not isinstance(rec, dict) or rec.get("schema") != SCHEMA or rec.get("design") != name
                    or rec.get("version") != i or int(_FILE.match(p.name).group(1)) != i):
                raise StateCorrupt(f"{name}/{p.name}：模式、设计名或版本号不符（链不连续？）")
            if rec.get("parent_sha256") != (prev["sha256"] if prev else None) or rec.get("parent_version") != (i - 1 or None):
                raise StateCorrupt(f"{name}/{p.name}：父版本链不符")
            try:
                ok = spec_sha256(rec["spec"]) == rec["sha256"]
            except (KeyError, TypeError, ValueError):
                ok = False
            if not ok:
                raise StateCorrupt(f"{name}/{p.name}：spec 与记录的 sha256 不符")
            if "source" in rec or "source_sha256" in rec:
                try:
                    check_source(rec["source"])
                    ok = spec_sha256(rec["source"]) == rec["source_sha256"]
                except (KeyError, TypeError, ValueError):
                    ok = False
                if not ok:
                    raise StateCorrupt(f"{name}/{p.name}：source 不合格或与 source_sha256 不符")
            try:
                _check_ownership(prev, rec)
            except (ValueError, KeyError) as e:
                raise StateCorrupt(f'{name}/{p.name}: {e}') from e
            out.append(rec)
            prev = rec
        errs = chain_errors(out)          # v0.15 OPT3：优化修订来源链（旧记录无 optimization 字段，不受影响）
        if errs:
            raise StateCorrupt(f"{name}：优化修订来源链损坏：{errs[0]['code']}（版本 {errs[0]['version']}）")
        return out

    def head(self, name):
        h = self.history(name)
        return h[-1] if h else None

    def append(self, name, rec):
        d = self._dir(name)
        _check_append(name, self.head(name), rec)
        d.mkdir(parents=True, exist_ok=True)
        data = json.dumps(rec, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=d)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            try:
                os.link(tmp, d / f"{rec['version']:08d}.json")      # 目标已存在即失败：不覆盖他人写入的版本
            except FileExistsError as e:
                raise VersionConflict(f"设计 {name} 的版本 {rec['version']} 已被其他写者占用") from e
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def names(self):
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and _NAME.match(p.name))


# ================================================================ v0.15 OPT3：接收优化修订（父哈希链 + 来源链校验）
# 一条设计链上的真源文档按"导入（source_import）→ 优化修订（optimizer_revision）→ …"排列。优化修订记录额外带
#   "optimization": {"parent_source_sha256", "declaration_id", "declaration_sha256", "declaration"(全文),
#                    "solver": {"solver", "kernel_sources_sha256"}, "variables": [名]}
# 提交时逐项校验（ProvenanceError 拒绝，状态不变）：
#   (1) 父哈希链：父 = 当前头记录的 source，parent_source_sha256 必须等于头记录 source_sha256（断链/伪造父哈希即拒绝）；
#   (2) 声明：declaration 全文的 sha256 等于 declaration_sha256；
#   (3) 求解器指纹：与当前内核 solver_fingerprint() 相同（提交方须是产生该修订的同一份内核源码）；
#   (4) 写回文档的来源链：每个设计变量 provenance=optimizer，其 source 同时写着父文档 sha256、声明 sha256 与内核指纹前缀；
#       文档 note 写着父文档 sha256；
#   (5) 文档其余条目相对父文档只允许：设计变量改值、document_limits 新增约束、tip_shortening 新增选择器（及其锁定的 k_X_i 移除）；
#       证据区逐项不变。
# 加载（FileStore.history）时对优化修订再核 (1)(2) 与 spec 字段一致性（不核 (3)：历史记录允许由旧内核产生）。
OPT_KIND = "optimizer_revision"
IMPORT_KIND = "source_import"


class ProvenanceError(ValueError):
    """优化修订的来源链校验失败；errors 为逐项 {"code","message"}。"""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("；".join(f"{e['code']}：{e['message']}" for e in self.errors[:6]))


def import_record(name, head, source, note):
    """把一份 math-source/2 文档作为链上的"导入"记录（无父优化关系；head 为当前头，可为 None）。"""
    sha = spec_sha256(source)
    spec = {"kind": IMPORT_KIND, "source_id": source.get("id"), "source_sha256": sha}
    return make_record(name, head, spec, None, {"kind": IMPORT_KIND, "note": note}, None, None, source=source)


def commit_source(store, name, source, note):
    rec = import_record(name, store.head(name), source, note)
    store.append(name, rec)
    return rec


def _tag_errors(new_doc, prov):
    errs = []
    psha, dsha = prov["parent_source_sha256"], prov["declaration_sha256"]
    ksha = (prov.get("solver") or {}).get("kernel_sources_sha256") or ""
    for n in prov.get("variables") or []:
        row = (new_doc.get("inputs") or {}).get(n)
        if row is None:
            errs.append({"code": "variable_missing", "message": f"写回文档 inputs 区没有设计变量 {n}"})
            continue
        src = row.get("source", "")
        if row.get("provenance") != "optimizer":
            errs.append({"code": "variable_provenance", "message": f"{n} 的 provenance 须为 optimizer"})
        if f"sha256={psha}" not in src:
            errs.append({"code": "source_chain_parent_mismatch", "message": f"{n} 的来源未写父文档 sha256={psha[:16]}…（伪造或断链）"})
        if f"sha256={dsha}" not in src:
            errs.append({"code": "source_chain_declaration_mismatch", "message": f"{n} 的来源未写声明 sha256={dsha[:16]}…"})
        if not ksha or ksha[:16] not in src:
            errs.append({"code": "source_chain_solver_mismatch", "message": f"{n} 的来源未写求解器指纹 {ksha[:16]}…"})
    if f"sha256={psha}" not in (new_doc.get("note") or ""):
        errs.append({"code": "note_parent_mismatch", "message": "写回文档 note 未写父文档 sha256"})
    return errs


def _diff_errors(parent, new_doc, decl, prov):
    """父文档 → 写回文档：只允许声明允许的变化。"""
    errs = []
    var = set(prov.get("variables") or [])
    p = (decl.get("parameters") or {})
    tip_added = "adapter.tip_shortening" in new_doc.get("selectors", {}) and "adapter.tip_shortening" not in parent.get("selectors", {})
    for n in set(parent.get("inputs", {})) | set(new_doc.get("inputs", {})):
        if n in var:
            continue
        a, b = parent["inputs"].get(n), new_doc["inputs"].get(n)
        if a == b:
            continue
        if b is None and tip_added and n in ("k_X_1", "k_X_2"):
            continue
        errs.append({"code": "unexpected_input_change", "message": f"inputs.{n} 不是设计变量却被改动"})
    if parent.get("evidence") != new_doc.get("evidence"):
        errs.append({"code": "evidence_changed", "message": "证据区被改动（优化修订只能保持证据）"})
    lims = p.get("document_limits") or {}
    for n in set(parent.get("constraints", {})) | set(new_doc.get("constraints", {})):
        a, b = parent["constraints"].get(n), new_doc["constraints"].get(n)
        if a == b or (a is None and n in lims):
            continue
        errs.append({"code": "unexpected_constraint_change", "message": f"constraints.{n} 被改动（只允许 document_limits 新增）"})
    for n in set(parent.get("selectors", {})) | set(new_doc.get("selectors", {})):
        a, b = parent["selectors"].get(n), new_doc["selectors"].get(n)
        if a == b or (a is None and n == "adapter.tip_shortening" and b and b.get("value") == p.get("tip_shortening")):
            continue
        errs.append({"code": "unexpected_selector_change", "message": f"selectors.{n} 被改动"})
    if parent.get("editions") != new_doc.get("editions"):
        errs.append({"code": "editions_changed", "message": "版次区被改动"})
    return errs


def check_optimization_revision(head, new_doc, decl, prov, *, check_solver=True):
    """提交前校验；返回逐项错误（空 = 合格）。head：当前头记录（须含 source）。"""
    from ..kernel import declared as DC
    from ..kernel import gridprune as GP
    errs = []
    need = ("parent_source_sha256", "declaration_id", "declaration_sha256", "solver", "variables")
    miss = [k for k in need if not (prov or {}).get(k)]
    if miss:
        return [{"code": "provenance_missing", "message": f"优化来源缺字段 {miss}"}]
    if head is None or "source" not in head:
        return [{"code": "no_parent_in_store", "message": "设计链上还没有父文档：先用 commit_source 导入父文档，再提交优化修订"}]
    if head["source_sha256"] != prov["parent_source_sha256"]:
        errs.append({"code": "broken_chain", "message": f"父哈希 {prov['parent_source_sha256'][:16]}… ≠ 当前头文档 "
                                                        f"{head['source_sha256'][:16]}…（断链、过期或伪造父哈希）"})
    if DC.declaration_sha256(decl) != prov["declaration_sha256"] or decl.get("id") != prov["declaration_id"]:
        errs.append({"code": "declaration_hash_mismatch", "message": "声明全文 sha256/id 与来源记录不符"})
    if check_solver:
        fp = GP.solver_fingerprint()
        s = prov["solver"]
        if s.get("solver") != fp["solver"] or s.get("kernel_sources_sha256") != fp["kernel_sources_sha256"]:
            errs.append({"code": "solver_fingerprint_mismatch", "message": "求解器指纹与当前内核源码不符"})
    try:
        check_source(new_doc)
    except ValueError as e:
        errs.append({"code": "source_invalid", "message": str(e)})
        return errs
    errs += _tag_errors(new_doc, prov)
    errs += _diff_errors(head["source"], new_doc, decl, prov)
    return errs


def make_optimization_record(name, head, new_doc, decl, prov):
    errs = check_optimization_revision(head, new_doc, decl, prov)
    if errs:
        raise ProvenanceError(errs)
    sha = spec_sha256(new_doc)
    spec = {"kind": OPT_KIND, "source_id": new_doc["id"], "source_sha256": sha,
            "parent_source_sha256": prov["parent_source_sha256"], "declaration_sha256": prov["declaration_sha256"],
            "solver_kernel_sha256": prov["solver"]["kernel_sources_sha256"]}
    changes = [{"name": n, "before": head["source"]["inputs"][n]["value"], "after": new_doc["inputs"][n]["value"],
                "unit": new_doc["inputs"][n]["unit"]} for n in prov["variables"]]
    rec = make_record(name, head, spec, None, {"kind": OPT_KIND, "declaration_id": prov["declaration_id"]}, changes, None,
                      source=new_doc)
    rec["optimization"] = {"parent_source_sha256": prov["parent_source_sha256"], "declaration_id": prov["declaration_id"],
                           "declaration_sha256": prov["declaration_sha256"], "declaration": copy.deepcopy(decl),
                           "solver": {"solver": prov["solver"]["solver"],
                                      "kernel_sources_sha256": prov["solver"]["kernel_sources_sha256"]},
                           "variables": list(prov["variables"])}
    return rec


def commit_optimization(store, name, new_doc, decl, prov):
    """校验 + 追加（乐观锁沿用 append）。不合格抛 ProvenanceError，存储不变。"""
    rec = make_optimization_record(name, store.head(name), new_doc, decl, prov)
    store.append(name, rec)
    return rec


def chain_errors(records):
    """已存记录链的来源链复核（不核求解器指纹）：优化修订的父哈希 = 前一条记录的 source_sha256，声明全文哈希一致，spec 字段一致。"""
    from ..kernel import declared as DC
    errs, prev = [], None
    for rec in records:
        opt = rec.get("optimization")
        spec = rec.get("spec") or {}
        if spec.get("kind") in (OPT_KIND, IMPORT_KIND) and spec.get("source_sha256") != rec.get("source_sha256"):
            errs.append({"version": rec.get("version"), "code": "spec_source_mismatch", "message": "spec.source_sha256 与记录不符"})
        if opt is not None or spec.get("kind") == OPT_KIND:
            opt = opt or {}
            if prev is None or prev.get("source_sha256") != opt.get("parent_source_sha256") \
                    or spec.get("parent_source_sha256") != opt.get("parent_source_sha256"):
                errs.append({"version": rec.get("version"), "code": "broken_chain", "message": "优化修订的父文档哈希与前一条记录不符"})
            try:
                ok = DC.declaration_sha256(opt["declaration"]) == opt["declaration_sha256"] == spec.get("declaration_sha256")
            except (KeyError, TypeError, ValueError):
                ok = False
            if not ok:
                errs.append({"version": rec.get("version"), "code": "declaration_hash_mismatch", "message": "声明全文哈希不符"})
            else:
                errs += [dict(e, version=rec.get("version")) for e in _tag_errors(rec.get("source") or {}, opt)]
        prev = rec
    return errs


def revision_history(store, name):
    """修订历史（只读）：每条 {version, kind, source_id, source_sha256, parent_source_sha256, declaration_id, solver, changes}。"""
    rows = []
    for rec in store.history(name):
        spec, opt = rec.get("spec") or {}, rec.get("optimization") or {}
        rows.append({"version": rec["version"], "kind": spec.get("kind", "spec_edit"), "source_id": spec.get("source_id"),
                     "source_sha256": rec.get("source_sha256"), "parent_source_sha256": opt.get("parent_source_sha256"),
                     "declaration_id": opt.get("declaration_id"), "declaration_sha256": opt.get("declaration_sha256"),
                     "solver": opt.get("solver"), "changes": rec.get("diff") if spec.get("kind") == OPT_KIND else None})
    return rows
