"""gears.system-input/1：系统层输入（轴、支承、轴承、键、过盈、油品、热参数、制造参数表补充项）。

格式见 docs/系统层输入-schema.md，模式见 data/schema/gears.system-input-1.schema.json。

叶子值一律带来源：
  {"value": 数值|字符串|布尔|对象|null, "unit": "mm", "source": "出处"}      显式值；value 为 null 表示"无来源，留空"→ 阻断
  {"from_design": "量名", "unit": "rpm", "source": "说明"}                   引用设计真源模型的求值结果（换算到 unit），不复制数值
特殊取值 "not_requested" / "not_applicable" 只允许出现在 EXPLICIT_NONE_KEYS 中（调用方显式声明"不算/不适用"），
解析为 None 传给已有模块（这些模块把 None 定义为显式声明，而不是缺省）。
本模块不设任何默认值；不在叶子里的结构（列表、按 id 的字典）原样保留。
"""
from __future__ import annotations

import copy
import json
import pathlib

from ..kernel import source_doc as SD
from ..kernel import units as U

SCHEMA_ID = "gears.system-input/1"
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "data" / "schema" / "gears.system-input-1.schema.json"
DATA_DIR = ROOT / "data" / "system"
SECTIONS = ("gear_rating", "manufacturing", "oil", "scuffing", "micropitting", "shafts", "bearings", "keys", "fits",
            "thermal")
EXPLICIT_NONE_TOKENS = ("not_requested", "not_applicable")
EXPLICIT_NONE_KEYS = ("a_ISO_inputs", "M_tmax", "f_L", "M_tRmin", "Rm_hub", "relative_axial_load", "fatigue", "static",
                      "B_M", "lambda_M", "c_v", "shear_factor", "sigma_dFK")
# 已有系统层模块的单位口径（见各模块 docstring）；表中键的 unit 必须逐字一致，否则判为无效输入（不做隐式换算）
EXPECTED_UNITS = {
    **{k: "mm" for k in ("x_A", "x_B", "x", "x0", "x1", "d", "d_i", "d_w", "h", "t1", "l_tr", "D_F", "D_aA", "D_iI",
                         "l_F", "U", "Rz_A", "Rz_I")},
    **{k: "N" for k in ("C_r", "C_0r", "F_r", "F_a", "F_tw")},
    **{k: "N*mm" for k in ("T", "M_tnenn", "M_tmax", "M_tRmin", "T_required")},
    **{k: "MPa" for k in ("Re_shaft", "Re_hub", "Re_key", "Rm_hub", "E_A", "E_I", "R_eLA", "R_eLI")},
    "n": "rpm", "required_life_h": "h",
    **{k: "kW" for k in ("P_A", "P_L", "P_N", "P_Q")},
    **{k: "deg" for k in ("alpha_wt_deg", "beta_w_deg", "theta_deg")},
    "nu_40": "mm^2/s", "nu_100": "mm^2/s", "theta_oil": "degC", "rho_15": "kg/m^3", "eta_oil": "mPa*s",
    "E": "MPa", "G": "MPa", "nu": "1", "direction_deg": "deg", "shear_factor": "1",
}
SHAFT_MODELS = ("statically_determinate", "beam")     # 显式轴模型选择（无默认；省略键 = 旧输入原路径）

_SCHEMA = None


def schema():
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


def load(ref):
    """ref：data/system 下的 id（如 'C001'）或 JSON 文件路径。"""
    p = pathlib.Path(ref)
    if not p.suffix:
        p = DATA_DIR / f"{ref}.system-input.json"
    return json.loads(p.read_text(encoding="utf-8"))


def sha256(doc):
    return SD.sha256_of(doc)


def is_leaf(node):
    return isinstance(node, dict) and "source" in node and ("value" in node or "from_design" in node)


def _walk_leaves(node, path):
    if is_leaf(node):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_leaves(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_leaves(v, f"{path}[{i}]")


def validate(doc):
    """结构（JSON Schema 子集）+ 叶子规则。返回 [{"path","code","message"}]。"""
    errs = SD.validate_schema(doc, schema())
    if errs:
        return errs
    for sec in SECTIONS:
        if doc.get(sec) is None:
            continue
        for path, leaf in _walk_leaves(doc[sec], f"$.{sec}"):
            key = path.rsplit(".", 1)[-1].split("[")[0]
            if not isinstance(leaf.get("source"), str) or not leaf["source"].strip():
                errs.append({"path": path, "code": "missing_source", "message": "叶子值必须写来源（source）"})
            if "value" in leaf and "from_design" in leaf:
                errs.append({"path": path, "code": "ambiguous_leaf", "message": "value 与 from_design 只能二选一"})
            if "from_design" in leaf and not isinstance(leaf.get("unit"), str):
                errs.append({"path": path, "code": "missing_unit", "message": "from_design 必须给出目标单位 unit"})
            if leaf.get("value") in EXPLICIT_NONE_TOKENS and key not in EXPLICIT_NONE_KEYS:
                errs.append({"path": path, "code": "token_not_allowed",
                             "message": f"{leaf['value']!r} 只允许用于 {EXPLICIT_NONE_KEYS}"})
            exp = EXPECTED_UNITS.get(key)
            v = leaf.get("value")
            numeric = (isinstance(v, (int, float)) and not isinstance(v, bool)) or "from_design" in leaf
            if exp and numeric and leaf.get("unit") != exp:
                errs.append({"path": path, "code": "unit_mismatch",
                             "message": f"{key} 的单位须为 {exp}（已有模块口径，不做隐式换算），收到 {leaf.get('unit')!r}"})
    errs += _shaft_model_rules(doc)
    return errs


def _shaft_model_rules(doc):
    """shaft_model / beam 一致性（v0.17 SYSREG）：取值须在 SHAFT_MODELS 内；beam 块只与 "beam" 同用；
    "beam" 路线不得同时给 x_A/x_B/bearings（支承与轴承引用改由 beam.supports 给出），G 与 ν 不得同时给出。"""
    errs = []
    for i, sh in enumerate(doc.get("shafts") or []):
        base = f"$.shafts[{i}]"
        leaf = sh.get("shaft_model")
        if leaf is None:
            if "beam" in sh:
                errs.append({"path": f"{base}.beam", "code": "beam_without_shaft_model",
                             "message": "给出 beam 块时须显式声明 shaft_model = \"beam\""})
            continue
        v = leaf.get("value")
        if "from_design" in leaf or (v is not None and v not in SHAFT_MODELS):
            errs.append({"path": f"{base}.shaft_model", "code": "invalid_shaft_model",
                         "message": f"shaft_model 须为显式值 {SHAFT_MODELS}，收到 {v!r}"})
            continue
        if v == "statically_determinate" and "beam" in sh:
            errs.append({"path": f"{base}.beam", "code": "beam_block_not_used",
                         "message": "shaft_model = statically_determinate 时不得给 beam 块（避免二义）"})
        if v == "beam":
            for k in ("x_A", "x_B", "bearings"):
                if k in sh:
                    errs.append({"path": f"{base}.{k}", "code": "beam_conflicting_field",
                                 "message": f"shaft_model = beam 时 {k} 须省略：支承位置与轴承引用由 beam.supports 给出"})
            bm = sh.get("beam") or {}
            if "G" in bm and "nu" in bm:
                errs.append({"path": f"{base}.beam", "code": "ambiguous_shear_modulus",
                             "message": "G 与 nu 只能二选一（nu 时 G = E/(2(1+ν))）"})
    return errs


class Resolver:
    """把带来源的系统层输入解析成已有模块可直接使用的普通值；逐项记录来源、缺项、显式 None。

    design_values：设计真源模型求值结果（规范单位，量名 → 数值），供 from_design 叶子使用。"""

    def __init__(self, design_values):
        self.design_values = dict(design_values or {})
        self.sources, self.missing, self.explicit_none, self.errors = {}, [], [], []

    def resolve(self, node, path):
        if is_leaf(node):
            key = path.rsplit(".", 1)[-1].split("[")[0]
            if "from_design" in node:
                q = node["from_design"]
                if q not in self.design_values or self.design_values[q] is None:
                    self.missing.append(f"{path}（设计模型量 {q} 不可得）")
                    return None
                try:
                    v = U.from_canonical(self.design_values[q], node["unit"])
                except KeyError as e:
                    self.errors.append({"path": path, "code": "unknown_unit", "message": str(e)})
                    return None
                self.sources[path] = f"设计模型 {q} → {node['unit']}；{node['source']}"
                return v
            v = node.get("value")
            if v is None:
                self.missing.append(path)
                return None
            if v in EXPLICIT_NONE_TOKENS:
                if key not in EXPLICIT_NONE_KEYS:
                    self.errors.append({"path": path, "code": "token_not_allowed", "message": f"{v!r} 不允许用于 {key}"})
                self.explicit_none.append(path)
                self.sources[path] = f"显式声明 {v}：{node['source']}"
                return None
            self.sources[path] = node["source"]
            return copy.deepcopy(v)
        if isinstance(node, dict):
            return {k: self.resolve(v, f"{path}.{k}") for k, v in node.items()}
        if isinstance(node, list):
            return [self.resolve(v, f"{path}[{i}]") for i, v in enumerate(node)]
        return node
