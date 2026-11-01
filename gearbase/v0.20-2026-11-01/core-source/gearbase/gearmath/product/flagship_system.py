"""M36 第 3 条门（v0.17 SYSREG）：H2 / W2W / P2 原旗舰 → 系统问题模板 → 统一 design_check；编辑用例回归。

流程（只读、无隐式默认）：
  1. 源文档 data/flagships-system/<族>.system-source.json（显式声明）+ 原 Stage0 需求 data/flagships-stage0/<族>.json；
  2. 经原 flagship_workflow（compile → 原 Stage0 求解 → 首选候选复查）得到候选；按源文档 candidate_rank 取用；
  3. 编译为系统问题模板：齿轮副 + 轴 + 轴承 + 键（可选，须声明）。每个叶子 {value, unit, source}：
     值只来自 Stage0 候选、原始需求参数、源文档显式声明，或由它们经下列运动学/静力关系派生（逐项写明来源）；
     没有来源的叶子 value = null → blocked，并进入 missing 清单。族/部件超出已收录模型时列入 unsupported；
  4. 模板 → gears.system-input/1（轴、轴承、键：design_check 同一次调用）+ 每个圆柱齿轮级一份
     gears.math-source/2 部分文档（gear_rating：design_check）。系统级"已求解" = 全部请求子检查 pass/fail。
派生关系（均为定义式/运动学，不含经验系数）：
  d = m_n·z/cos β（Stage0 的 H2 中心距模型 a = m_n(z1+z2)/(2cos β)，即 x1+x2 = 0 → d_w = d、α_wt = α_t、β_w = β）；
  α_t = atan(tan α_n / cos β)；F_t = 2·T/d（T 作用在该齿轮上）；n_小 = n_大·u；
  经啮合传递扭矩（T_1 = T_2/u）只在源文档显式声明 load_transfer = "nominal_lossless" 时使用（ISO 6336-1 名义载荷口径），
  否则阻断；W2W 各轴扭矩用原 Stage0 自身的恒摩擦效率模型（M31 SPEC §2-D）派生。
本模块不新增强度公式；蜗杆副/行星排的啮合力与强度评级未收录（M40 冻结）→ unsupported，不以 Stage0 代替系统评级。
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import pathlib

from ..gear import flagship_kinematics as FK
from ..gear import flagship_reference as FREF
from ..gear import flagship_h2 as FH2
from ..gear import flagship_p2 as FP2
from ..gear import flagship_w2w as FW2W
from ..gear import rating as RT
from ..tools import flagship_workflow as FW
from . import design_check as DC
from . import system_input as SIN

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "data" / "flagships-system"
STAGE0_DIR = ROOT / "data" / "flagships-stage0"
SOURCE_SCHEMA = "gearbase.flagship-system-source/1"
TEMPLATE_SCHEMA = "gearbase.flagship-system-template/1"
FAMILIES = ("H2", "W2W", "P2")
SYSTEM_SCOPES = ("shaft", "bearing", "key")
BEARING_FIELDS = (("bearing_kind", "-"), ("C_r", "N"), ("C_0r", "N"), ("xy", "-"), ("reliability_percent", "%"),
                  ("a_ISO_inputs", "-"), ("required_life_h", "h"))
MESH_LAYOUT = (("x", "mm"), ("theta_deg", "deg"), ("tangential_sign", "1"), ("axial_sign", "1"))
SHAFT_LAYOUT = (("x_A", "mm"), ("x_B", "mm"), ("axial_support", "-"))
DIRECT_MODELS = {"H2": FH2, "W2W": FW2W, "P2": FP2}
UNDECLARED = "未在旗舰原始数据或源文档显式声明中给出"


class SourceInvalid(ValueError):
    pass


# ------------------------------------------------------------------ 小工具
def _L(value, unit, source):
    return {"value": value, "unit": unit, "source": source}


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256(obj):
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()


def _decl(node, key, unit, why=UNDECLARED):
    """源文档中的显式叶子（单位须逐字一致），否则 null 叶子（缺项）。"""
    leaf = (node or {}).get(key)
    if leaf is None:
        return _L(None, unit, why)
    if not SIN.is_leaf(leaf) or "from_design" in leaf:
        raise SourceInvalid(f"{key}：须为 {{value, unit, source}} 叶子")
    if leaf.get("value") is not None and leaf.get("unit") != unit:
        raise SourceInvalid(f"{key}：单位须为 {unit}，收到 {leaf.get('unit')!r}")
    return copy.deepcopy(leaf)


def _v(leaf):
    return leaf["value"]


def _derive(fn, unit, source, *leaves):
    vals = [_v(x) for x in leaves]
    if any(v is None for v in vals):
        miss = "、".join(x["source"] for x in leaves if x["value"] is None)
        return _L(None, unit, f"派生不可得（缺输入）：{source}；缺：{miss}")
    return _L(fn(*vals), unit, f"派生：{source}")


def leaves(node, path="$"):
    """模板中的全部叶子（路径 → 叶子）。"""
    if isinstance(node, dict) and "source" in node and "value" in node and "unit" in node:
        yield path, node
    elif isinstance(node, dict):
        for k in sorted(node):
            yield from leaves(node[k], f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from leaves(v, f"{path}[{i}]")


def _validate_source(src, req):
    if not isinstance(src, dict) or src.get("schema") != SOURCE_SCHEMA:
        raise SourceInvalid(f"源文档 schema 须为 {SOURCE_SCHEMA}")
    if src.get("family") not in FAMILIES or not isinstance(src.get("id"), str):
        raise SourceInvalid("源文档须给出 family ∈ H2/W2W/P2 与 id")
    if not isinstance(req, dict) or req.get("family") != src["family"]:
        raise SourceInvalid("Stage0 需求族与源文档不一致")
    rank = (src.get("candidate_rank") or {}).get("value")
    if type(rank) is not int or rank < 1:
        raise SourceInvalid("candidate_rank 须显式给出（正整数，原 Stage0 排序名次）")
    lt = (src.get("load_transfer") or {}).get("value")
    if lt not in (None, "nominal_lossless"):
        raise SourceInvalid("load_transfer 只接受 'nominal_lossless'（或不声明 → 阻断经啮合的扭矩传递）")


# ------------------------------------------------------------------ 公共部件
def _mesh_load(src_shaft, name, F_tw, d_w, alpha_wt, beta_w):
    lay = ((src_shaft or {}).get("meshes") or {}).get(name) or {}
    ld = {"kind": "mesh", "name": name, "F_tw": F_tw, "d_w": d_w, "alpha_wt_deg": alpha_wt, "beta_w_deg": beta_w}
    for k, u in MESH_LAYOUT:
        ld[k] = _decl(lay, k, u, f"{UNDECLARED}（啮合 {name} 的 {k}）")
    return ld


def _torque_load(src_shaft, name, magnitude):
    """扭矩载荷：幅值可派生；符号取决于转向/啮合方位，须源文档显式声明 torque_sign（±1）。"""
    sgn = _decl(src_shaft, "torque_sign", "1", f"{UNDECLARED}（{name} 扭矩符号取决于转向与啮合方位）")
    T = _derive(lambda s, m: s * m, "N*mm", f"T = torque_sign·|T|（{magnitude['source']}）", sgn, magnitude)
    return {"kind": "torque", "name": name,
            "x": _decl(src_shaft, "torque_x", "mm", f"{UNDECLARED}（{name} 联轴器/输出端轴向位置）"), "T": T}


def _shaft(src, sid, note, loads, bearing_ids, n_leaf):
    s = (src.get("shafts") or {}).get(sid) or {}
    out = {"id": sid, "note": note}
    for k, u in SHAFT_LAYOUT:
        out[k] = _decl(s, k, u)
    out["segments"] = copy.deepcopy(s["segments"]) if s.get("segments") is not None else None
    out["sections"] = copy.deepcopy(s["sections"]) if s.get("sections") is not None else None
    out["loads"] = loads
    out["bearings"] = dict(zip(("A", "B"), bearing_ids))
    out["speed"] = n_leaf
    return out


def _bearings(T, src, shaft):
    for bid in shaft["bearings"].values():
        b = (src.get("bearings") or {}).get(bid) or {}
        rec = {k: _decl(b, k, u) for k, u in BEARING_FIELDS}
        n = copy.deepcopy(shaft["speed"])
        n["source"] = f"{n['source']}（轴 {shaft['id']} 转速）"
        rec["n"] = n
        T["bearings"][bid] = rec


def _keys(T, src):
    if src.get("keys") is None:
        T["keys"] = None
        T["missing_structural"].append("$.keys（轴毂连接方式与键参数：" + UNDECLARED + "）")
    else:
        T["keys"] = copy.deepcopy(src["keys"])


# ------------------------------------------------------------------ H2（两级平行轴斜齿）
def _h2(T, src, p, cand):
    lossless = (src.get("load_transfer") or {}).get("value") == "nominal_lossless"
    op = src.get("operating") or {}
    T["operating"] = {"T_out": _decl(op, "T_out", "N*mm"), "n_out": _decl(op, "n_out", "rpm")}
    if lossless:
        T["operating"]["load_transfer"] = copy.deepcopy(src["load_transfer"])
    Tout, nout = T["operating"]["T_out"], T["operating"]["n_out"]
    g = {}
    for k in ("stage1", "stage2"):
        st = cand[k]
        base = f"Stage0 候选 #{T['stage0']['candidate_rank']} {k}"
        z1, z2 = _L(st["z1"], "1", f"{base}.z1"), _L(st["z2"], "1", f"{base}.z2")
        mn, beta = _L(st["mn_mm"], "mm", f"{base}.mn_mm"), _L(st["beta_deg"], "deg", f"{base}.beta_deg")
        a_n = _decl((src.get("stages") or {}).get(k), "alpha_n", "deg", f"{UNDECLARED}（{k} 法向压力角；Stage0 几何不含 α_n）")
        d1 = _derive(lambda m, z, b: m * z / math.cos(math.radians(b)), "mm", f"d1 = m_n·z1/cos β（{base}）", mn, z1, beta)
        d2 = _derive(lambda m, z, b: m * z / math.cos(math.radians(b)), "mm", f"d2 = m_n·z2/cos β（{base}）", mn, z2, beta)
        u = _derive(lambda a, b: b / a, "1", f"u = z2/z1（{base}）", z1, z2)
        awt = _derive(lambda a, b: math.degrees(math.atan(math.tan(math.radians(a)) / math.cos(math.radians(b)))), "deg",
                      f"α_wt = α_t = atan(tan α_n/cos β)（x1+x2 = 0，{base}）", a_n, beta)
        g[k] = {"z_1": z1, "z_2": z2, "m_n": mn, "beta": beta, "alpha_n": a_n, "d_1": d1, "d_2": d2, "u": u, "alpha_wt": awt}
    s1, s2 = g["stage1"], g["stage2"]
    D = T["derived"]
    D["n_mid"] = _derive(lambda n, u: n * u, "rpm", "n_mid = n_out·u2", nout, s2["u"])
    D["n_in"] = _derive(lambda n, u: n * u, "rpm", "n_in = n_mid·u1", D["n_mid"], s1["u"])
    D["stage2.F_t"] = _derive(FK.tangential_force, "N", "F_t2 = 2·T_out/d2(stage2)（T_out 作用于二级大轮）", Tout, s2["d_2"])
    if lossless:
        D["T_mid"] = _derive(lambda t, u: t / u, "N*mm", "T_mid = T_out/u2（load_transfer = nominal_lossless，ISO 6336-1 名义载荷）",
                             Tout, s2["u"])
    else:
        D["T_mid"] = _L(None, "N*mm", "派生不可得：T_mid = T_out/u2 需源文档显式声明 load_transfer（名义无损口径）或给定级效率；"
                                      "H2 原始数据未给效率")
    D["T_in"] = _derive(lambda t, u: t / u, "N*mm", "T_in = T_mid/u1", D["T_mid"], s1["u"])
    D["stage1.F_t"] = _derive(FK.tangential_force, "N", "F_t1 = 2·T_mid/d2(stage1)", D["T_mid"], s1["d_2"])
    for k, n1, t1 in (("stage1", D["n_in"], D["T_in"]), ("stage2", D["n_mid"], D["T_mid"])):
        gi = {kk: g[k][kk] for kk in ("z_1", "z_2", "m_n", "beta", "alpha_n")}
        gi["n_1"] = n1
        gi["T_1"] = _derive(lambda t: t / 1000.0, "N*m", f"T_1 = 小轮扭矩（{t1['source']}）", t1)
        T["gear_pairs"][k] = {"kind": "cylindrical_helical_external", "inputs": gi,
                              "geometry": {kk: g[k][kk] for kk in ("d_1", "d_2", "u", "alpha_wt")}}
    ss = src.get("shafts") or {}
    T["shafts"] = [
        _shaft(src, "S1", "H2 输入轴（一级小轮）",
               [_mesh_load(ss.get("S1"), "stage1", D["stage1.F_t"], s1["d_1"], s1["alpha_wt"], s1["beta"]),
                _torque_load(ss.get("S1"), "输入扭矩", _derive(lambda t: abs(t), "N*mm", "|T_in|", D["T_in"]))],
               ("S1.A", "S1.B"), D["n_in"]),
        _shaft(src, "S2", "H2 中间轴（一级大轮 + 二级小轮）",
               [_mesh_load(ss.get("S2"), "stage1", D["stage1.F_t"], s1["d_2"], s1["alpha_wt"], s1["beta"]),
                _mesh_load(ss.get("S2"), "stage2", D["stage2.F_t"], s2["d_1"], s2["alpha_wt"], s2["beta"])],
               ("S2.A", "S2.B"), D["n_mid"]),
        _shaft(src, "S3", "H2 输出轴（二级大轮）",
               [_mesh_load(ss.get("S3"), "stage2", D["stage2.F_t"], s2["d_2"], s2["alpha_wt"], s2["beta"]),
                _torque_load(ss.get("S3"), "输出扭矩", _derive(lambda t: abs(t), "N*mm", "|T_out|", Tout))],
               ("S3.A", "S3.B"), nout)]


# ------------------------------------------------------------------ W2W（两级蜗杆）
def _w2w(T, src, p, cand):
    T["operating"] = {"T_out": _L(p["t_out_nm"] * 1000.0, "N*mm", "Stage0 需求 parameters.t_out_nm"),
                      "n_in": _L(p["n1_rpm"], "rpm", "Stage0 需求 parameters.n1_rpm")}
    D = T["derived"]
    base = f"Stage0 候选 #{T['stage0']['candidate_rank']}"
    one, two = cand["stage1"], cand["stage2"]
    D["n_mid"] = _L(cand["n_mid_rpm"], "rpm", f"{base}.n_mid_rpm")
    D["n_out"] = _L(cand["n_out_rpm"], "rpm", f"{base}.n_out_rpm")
    D["T_mid"] = _L(p["t_out_nm"] * 1000.0 / (two["ratio"] * two["eta"]), "N*mm",
                    f"派生：T_mid = T_out/(i2·η2)，η2 = {base}.stage2.eta（M31 SPEC §2-D 恒摩擦效率模型）")
    D["T_in"] = _L(D["T_mid"]["value"] / (one["ratio"] * one["eta"]), "N*mm",
                   f"派生：T_in = T_mid/(i1·η1)，η1 = {base}.stage1.eta")
    D["stage1.F_t2"] = _L(2.0 * D["T_mid"]["value"] / one["d2_mm"], "N", f"派生：蜗轮切向力 F_t2 = 2·T_mid/d2（{base}.stage1.d2_mm）")
    D["stage2.F_t2"] = _L(2.0 * T["operating"]["T_out"]["value"] / two["d2_mm"], "N",
                          f"派生：蜗轮切向力 F_t2 = 2·T_out/d2（{base}.stage2.d2_mm）")
    for k, st in (("stage1", one), ("stage2", two)):
        T["gear_pairs"][k] = {"kind": "worm", "inputs": {
            "m": _L(st["m_mm"], "mm", f"{base}.{k}.m_mm"), "q": _L(st["q"], "1", f"{base}.{k}.q"),
            "z_1": _L(st["z1"], "1", f"{base}.{k}.z1"), "z_2": _L(st["z2"], "1", f"{base}.{k}.z2"),
            "gamma_deg": _L(st["gamma_deg"], "deg", f"{base}.{k}.gamma_deg"), "eta": _L(st["eta"], "1", f"{base}.{k}.eta"),
            "b_2": _decl((src.get("stages") or {}).get(k), "b_2", "mm"),
            "material_pair": _decl((src.get("stages") or {}).get(k), "material_pair", "-")}}
        T["unsupported"].append({"component": f"gear_pairs.{k}", "reason": "蜗杆副强度/磨损/胶合评级未收录（M40 冻结），design_check 无蜗杆族"})
    for sid, note, n in (("S1", "W2W 输入蜗杆轴", T["operating"]["n_in"]), ("S2", "W2W 中间轴（一级蜗轮 + 二级蜗杆）", D["n_mid"]),
                         ("S3", "W2W 输出轴（二级蜗轮）", D["n_out"])):
        sh = _shaft(src, sid, note, None, (f"{sid}.A", f"{sid}.B"), n)
        T["shafts"].append(sh)
        T["unsupported"].append({"component": f"shafts.{sid}.loads",
                                 "reason": "蜗杆副啮合力（含摩擦角的三向分力）在 shaft_line 中未收录（M40 冻结）→ 轴载荷不可编译"})
    T["stage0_thermal"] = {"thermal_ok": cand["thermal_ok"], "t_oil_est_c": cand["t_oil_est_c"],
                           "area_required_m2": cand["area_required_m2"], "note": "原 Stage0 热平衡（M31 SPEC §2-C），保留原失败项"}


# ------------------------------------------------------------------ P2（两级 NGW 行星）
def _p2(T, src, p, cand):
    T["operating"] = {"n_in": _L(p["n1_rpm"], "rpm", "Stage0 需求 parameters.n1_rpm"),
                      "T_out": _decl(src.get("operating"), "T_out", "N*mm", f"{UNDECLARED}（P2 原始需求不含扭矩/功率）")}
    D = T["derived"]
    base = f"Stage0 候选 #{T['stage0']['candidate_rank']}"
    D["n_mid"] = _L(cand["n_mid_rpm"], "rpm", f"{base}.n_mid_rpm")
    D["n_out"] = _L(cand["n_out_rpm"], "rpm", f"{base}.n_out_rpm")
    for k in ("stage1", "stage2"):
        st = cand[k]
        m = _decl((src.get("stages") or {}).get(k), "m", "mm",
                  f"{UNDECLARED}（Stage0 只给模数候选 m_options = {st['m_options']}，未选定）")
        T["gear_pairs"][k] = {"kind": "planetary_ngw", "inputs": {
            "z_s": _L(st["zs"], "1", f"{base}.{k}.zs"), "z_p": _L(st["zp"], "1", f"{base}.{k}.zp"),
            "z_r": _L(st["zr"], "1", f"{base}.{k}.zr"), "n_p": _L(st["n_p"], "1", f"{base}.{k}.n_p"), "m": m}}
        T["unsupported"].append({"component": f"gear_pairs.{k}", "reason": "行星排载荷分配/强度评级未收录（M40 冻结），design_check 无行星族"})
    for sid, note, n in (("S1", "P2 输入太阳轮轴", T["operating"]["n_in"]), ("S2", "P2 中间轴（一级行星架 + 二级太阳轮）", D["n_mid"]),
                         ("S3", "P2 输出行星架轴", D["n_out"])):
        T["shafts"].append(_shaft(src, sid, note, None, (f"{sid}.A", f"{sid}.B"), n))
        T["unsupported"].append({"component": f"shafts.{sid}.loads",
                                 "reason": "行星排多啮合点均载/浮动构件载荷模型在 shaft_line 中未收录 → 轴载荷不可编译"})


BUILDERS = {"H2": _h2, "W2W": _w2w, "P2": _p2}


# ------------------------------------------------------------------ 编译
def compile_template(source, requirement):
    """源文档 + 原 Stage0 需求 → 系统问题模板（不读写文件，不改调用方对象）。"""
    src, req = copy.deepcopy(source), copy.deepcopy(requirement)
    _validate_source(src, req)
    wf = FW.run({"action": "run", "requirement": req})
    T = {"schema": TEMPLATE_SCHEMA, "family": src["family"], "id": src["id"], "source_sha256": sha256(src),
         "requirement_sha256": FW.requirement_sha256(req), "status": None,
         "stage0": {"status": wf.get("status"), "outcome": wf.get("outcome"),
                    "candidate_rank": src["candidate_rank"]["value"], "candidate": None,
                    "verification": wf.get("verification")},
         "operating": {}, "gear_pairs": {}, "shafts": [], "bearings": {}, "keys": None, "derived": {},
         "unsupported": [], "missing_structural": [], "missing": []}
    if wf.get("status") != "completed_stage0":
        T["status"] = "blocked_stage0"
        T["stage0"]["errors"] = wf.get("errors") or wf.get("questions")
        return T
    cands = wf["result"]["candidates"]
    rank = src["candidate_rank"]["value"]
    if rank > len(cands):
        T["status"] = "blocked_stage0"
        T["stage0"]["errors"] = [f"candidate_rank {rank} 超出原 Stage0 返回的 {len(cands)} 个候选"]
        return T
    T["stage0"]["candidate"] = copy.deepcopy(cands[rank - 1])
    BUILDERS[src["family"]](T, src, req["parameters"], T["stage0"]["candidate"])
    for sh in T["shafts"]:
        _bearings(T, src, sh)
        for k in ("segments", "sections"):
            if sh[k] is None:
                T["missing_structural"].append(f"$.shafts[{sh['id']}].{k}（{UNDECLARED}）")
    _keys(T, src)
    T["missing"] = sorted(p for p, lf in leaves({k: T[k] for k in ("operating", "gear_pairs", "shafts", "bearings", "derived")})
                          if lf["value"] is None)
    T["status"] = "template_compiled"
    return T


def _strip(leaf):
    return {"value": leaf["value"], "unit": leaf["unit"], "source": leaf["source"]}


def to_system_input(T):
    """模板 → gears.system-input/1（轴、轴承、键）。不可编译的轴载荷（unsupported）给 None → design_check 阻断列缺项。"""
    shafts = []
    for sh in T["shafts"]:
        loads = None
        if sh["loads"] is not None:
            loads = []
            for ld in sh["loads"]:
                if ld["kind"] == "mesh":
                    loads.append({"kind": "mesh", "name": ld["name"], "x": _strip(ld["x"]), "F_tw": _strip(ld["F_tw"]),
                                  "d_w": _strip(ld["d_w"]), "alpha_wt_deg": _strip(ld["alpha_wt_deg"]),
                                  "beta_w_deg": _strip(ld["beta_w_deg"]), "theta_deg": _strip(ld["theta_deg"]),
                                  "tangential_sign": _strip(ld["tangential_sign"]), "axial_sign": _strip(ld["axial_sign"])})
                else:
                    loads.append({"kind": "torque", "name": ld["name"], "x": _strip(ld["x"]), "T": _strip(ld["T"])})
        shafts.append({"id": sh["id"], "note": sh["note"], "x_A": _strip(sh["x_A"]), "x_B": _strip(sh["x_B"]),
                       "axial_support": _strip(sh["axial_support"]), "segments": copy.deepcopy(sh["segments"]),
                       "loads": loads, "sections": copy.deepcopy(sh["sections"]), "bearings": dict(sh["bearings"])})
    bearings = {bid: {k: _strip(v) for k, v in b.items()} for bid, b in T["bearings"].items()}
    return {"schema": SIN.SCHEMA_ID, "id": T["id"], "title": f"{T['family']} 旗舰系统问题模板（flagship_system 编译）",
            "design_ref": {"source_id": T["id"], "model_family": None,
                           "source": "flagship_system.to_system_input：全部叶子显式值，无设计模型引用"},
            "assumptions": [{"text": u["reason"], "source": u["component"]} for u in T["unsupported"]],
            "shafts": shafts, "bearings": bearings, "keys": copy.deepcopy(T["keys"])}


def to_gear_design_doc(T, stage):
    """圆柱齿轮级 → gears.math-source/2 部分文档（只含有来源的输入；缺项由 rate 阻断）。"""
    gp = T["gear_pairs"][stage]
    src_stage = ((T.get("_source") or {}).get("stages") or {}).get(stage) or {}
    inputs = {}
    for k, lf in gp["inputs"].items():
        if lf["value"] is not None:
            prov = "optimizer" if lf["source"].startswith("Stage0") else "user"
            inputs[k] = {"value": float(lf["value"]), "unit": lf["unit"], "provenance": prov, "source": lf["source"]}
    for k, lf in (src_stage.get("gear_inputs") or {}).items():
        inputs.setdefault(k, copy.deepcopy(lf))
    return {"schema": "gears.math-source/2", "id": f"{T['id']}.{stage}", "title": f"{T['family']} {stage}（flagship_system 编译）",
            "note": "部分文档：只含 Stage0 几何、源文档声明及派生量；其余输入未声明 → rate 阻断",
            "inputs": inputs, "constraints": copy.deepcopy(src_stage.get("constraints") or {}),
            "evidence": copy.deepcopy(src_stage.get("evidence") or {}),
            "selectors": copy.deepcopy(src_stage.get("selectors") or {}),
            "editions": copy.deepcopy(src_stage.get("editions") or {})}


def gear_rating_missing(doc):
    """圆柱副统一模型（rating.pair_model，按文档选择器）所需输入 − 文档已给 = 缺项；另列缺选择器与版次。"""
    sel = {k: r["value"] for k, r in doc["selectors"].items()}
    try:
        specs = RT.pair_model(selectors={k: v for k, v in sel.items() if k.startswith("method.")}).specs
    except Exception:  # noqa: BLE001 —— 非法选择器由 design_check 报告
        specs = {}
    have = set(doc["inputs"]) | set(doc["constraints"]) | set(doc["evidence"])
    miss = [f"input:{k}" for k in sorted(set(specs) - have)]
    miss += [f"selector:{k}" for k in RT.required_selectors(sel) if k not in sel]
    miss += [f"edition:{e}" for e in ("ISO 21771", "ISO 6336-1", "ISO 6336-2", "ISO 6336-3") if e not in doc["editions"]]
    return miss


def solve(source, requirement):
    """编译 + 统一 design_check。返回 {template, checks, system_status, missing_by_scope}。"""
    T = compile_template(source, requirement)
    T["_source"] = copy.deepcopy(source)
    out = {"template": T, "checks": {}, "gear_rating": {}, "missing_by_scope": {}}
    if T["status"] != "template_compiled":
        T.pop("_source")
        out["system_status"] = "blocked"
        return out
    si = to_system_input(T)
    r = DC.check({"id": T["id"]}, si, list(SYSTEM_SCOPES))
    for s in SYSTEM_SCOPES:
        c = r["checks"][s]
        out["checks"][s] = {"status": c["status"], "missing": list(c["missing"]), "errors": [e.get("message", "") for e in c["errors"]],
                            "items": [(i["id"], i["value"], i["status"]) for i in c["items"]]}
        out["missing_by_scope"][s] = list(c["missing"])
    statuses = [out["checks"][s]["status"] for s in SYSTEM_SCOPES]
    for st, gp in T["gear_pairs"].items():
        if gp["kind"] != "cylindrical_helical_external":
            out["gear_rating"][st] = {"status": "blocked", "unsupported": True,
                                      "reason": next(u["reason"] for u in T["unsupported"] if u["component"] == f"gear_pairs.{st}")}
            statuses.append("blocked")
            continue
        doc = to_gear_design_doc(T, st)
        gsi = {"schema": SIN.SCHEMA_ID, "id": doc["id"],
               "design_ref": {"source_id": doc["id"], "model_family": "pair_model", "source": "flagship_system 编译"}}
        gr = DC.check(doc, gsi, ["gear_rating"])["checks"]["gear_rating"]
        miss = gear_rating_missing(doc)
        out["gear_rating"][st] = {"status": gr["status"], "missing": miss,
                                  "errors": [e.get("name") or e.get("message", "") for e in gr["errors"]],
                                  "items": [(i["id"], i["value"], i["status"]) for i in gr["items"]]}
        statuses.append(gr["status"])
    out["missing_by_scope"]["gear_rating"] = {st: g.get("missing", [g.get("reason")]) for st, g in out["gear_rating"].items()}
    T.pop("_source")
    out["system_status"] = "solved" if all(s in ("pass", "fail") for s in statuses) else "blocked"
    return out


# ------------------------------------------------------------------ 文件入口
def load_source(family):
    return json.loads((SRC_DIR / f"{family}.system-source.json").read_text(encoding="utf-8"))


def load_requirement(family, source=None):
    """读取原 Stage0 需求，并核对源文档登记的文件 sha256（不一致 → SourceInvalid）。"""
    src = source if source is not None else load_source(family)
    ref = src["stage0_requirement"]
    path = ROOT / ref["path"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise SourceInvalid(f"{ref['path']} 的 sha256 与源文档登记不一致")
    return json.loads(raw.decode("utf-8"))["requirement"]


def solve_family(family):
    src = load_source(family)
    return solve(src, load_requirement(family, src))


# ------------------------------------------------------------------ 编辑用例
def _set(doc, path, value):
    cur = doc
    for k in path[:-1]:
        cur = cur.setdefault(k, {})
    cur[path[-1]] = value


def _flat(T):
    keep = {k: T[k] for k in ("operating", "gear_pairs", "shafts", "bearings", "derived", "keys", "unsupported", "stage0",
                              "stage0_thermal", "missing", "missing_structural") if k in T}
    out = {}

    def walk(node, path):
        if isinstance(node, dict) and not ("value" in node and "source" in node and "unit" in node):
            for k in node:
                walk(node[k], f"{path}.{k}")
        elif isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        else:
            out[path] = _canon(node)
    walk(keep, "$")
    return out


def _indep_h2(p):
    """独立重算：直接调用原 H2 Stage0 模块（不经 flagship_workflow / 模板）。"""
    return FH2.run(p)["candidates"]


def _edits():
    """每个旗舰的编辑用例：(名称, 目标 'source'|'requirement', 路径, 新值, 观测量(模板→值), 独立重算(源,需求→值),
    允许变化的模板路径前缀)。观测量变化方向须与独立重算一致，允许前缀以外的模板内容须逐位不变。"""
    def h2_ft2(src, req):
        c = _indep_h2(req["parameters"])[src["candidate_rank"]["value"] - 1]["stage2"]
        return FREF.h2_output_tangential_force(torque_nmm=src["operating"]["T_out"]["value"],
                                               module_mm=c["mn_mm"], tooth_count=c["z2"], helix_deg=c["beta_deg"])

    def h2_nin(src, req):
        c = _indep_h2(req["parameters"])[src["candidate_rank"]["value"] - 1]
        return FK.two_stage_input_speed(src["operating"]["n_out"]["value"], c["stage2"]["z2"], c["stage2"]["z1"], c["stage1"]["z2"], c["stage1"]["z1"])

    def w2w_tin(src, req):
        p = req["parameters"]
        c = FW2W.run(p)["candidates"][src["candidate_rank"]["value"] - 1]
        return p["t_out_nm"] * 1000.0 / (c["stage2"]["ratio"] * c["stage2"]["eta"]) / (c["stage1"]["ratio"] * c["stage1"]["eta"])

    def w2w_toil(src, req):
        p = req["parameters"]
        c = FW2W.run(p)["candidates"][src["candidate_rank"]["value"] - 1]
        return p["t_amb_c"] + c["q_loss_w"] / (p["k_w_m2k"] * p["area_m2"])

    def p2_nout(src, req):
        p = req["parameters"]
        c = FP2.run(p)["candidates"][src["candidate_rank"]["value"] - 1]
        return p["n1_rpm"] / c["i_total"]

    def p2_itot(src, req):
        return FP2.run(req["parameters"])["candidates"][src["candidate_rank"]["value"] - 1]["i_total"]

    leaf = lambda v, u, s: {"value": v, "unit": u, "source": s}  # noqa: E731
    return {
        "H2": [
            ("T_out 600→750 N·m", "source", ("operating", "T_out"),
             leaf(750000.0, "N*mm", "编辑用例：用户把输出扭矩改为 750 N·m（演示编辑，不入库）"),
             lambda T: T["derived"]["stage2.F_t"]["value"], h2_ft2,
             ("$.operating.T_out", "$.derived.stage2.F_t", "$.shafts[1].loads[1].F_tw", "$.shafts[2].loads[0].F_tw",
              "$.shafts[2].loads[1].T")),
            ("n_out 150→120 rpm", "source", ("operating", "n_out"),
             leaf(120.0, "rpm", "编辑用例：用户把输出转速改为 120 rpm（演示编辑，不入库）"),
             lambda T: T["derived"]["n_in"]["value"], h2_nin,
             ("$.operating.n_out", "$.derived.n_in", "$.derived.n_mid", "$.gear_pairs.stage1.inputs.n_1",
              "$.gear_pairs.stage2.inputs.n_1", "$.shafts[0].speed", "$.shafts[1].speed", "$.shafts[2].speed",
              "$.bearings.S1.A.n", "$.bearings.S1.B.n", "$.bearings.S2.A.n", "$.bearings.S2.B.n", "$.bearings.S3.A.n",
              "$.bearings.S3.B.n")),
        ],
        "W2W": [
            ("t_out_nm 800→1000", "requirement", ("parameters", "t_out_nm"), 1000.0,
             lambda T: T["derived"]["T_in"]["value"], w2w_tin,
             ("$.operating.T_out", "$.derived.T_in", "$.derived.T_mid", "$.derived.stage1.F_t2", "$.derived.stage2.F_t2",
              "$.stage0.candidate.p_out_w", "$.stage0.candidate.p_in_w", "$.stage0.candidate.q_loss_w",
              "$.stage0.candidate.area_required_m2", "$.stage0.candidate.dt_actual_k", "$.stage0.candidate.t_oil_est_c",
              "$.stage0.candidate.thermal", "$.stage0.candidate.cooling_levers", "$.stage0.candidate.stage1.area_required_natconv_m2",
              "$.stage0_thermal")),
            ("area_m2 0.5→1.0", "requirement", ("parameters", "area_m2"), 1.0,
             lambda T: T["stage0"]["candidate"]["t_oil_est_c"], w2w_toil,
             ("$.stage0.candidate.area_provided_m2", "$.stage0.candidate.dt_actual_k", "$.stage0.candidate.t_oil_est_c",
              "$.stage0.candidate.thermal_ok", "$.stage0.candidate.thermal", "$.stage0_thermal", "$.stage0.outcome")),
        ],
        "P2": [
            ("n1_rpm 1440→960", "requirement", ("parameters", "n1_rpm"), 960.0,
             lambda T: T["derived"]["n_out"]["value"], p2_nout,
             ("$.operating.n_in", "$.derived.n_mid", "$.derived.n_out", "$.stage0.candidate.n_mid_rpm",
              "$.stage0.candidate.n_out_rpm", "$.shafts[0].speed", "$.shafts[1].speed", "$.shafts[2].speed",
              "$.bearings.S1.A.n", "$.bearings.S1.B.n", "$.bearings.S2.A.n", "$.bearings.S2.B.n", "$.bearings.S3.A.n",
              "$.bearings.S3.B.n")),
            ("target_total_ratio 40→36", "requirement", ("parameters", "target_total_ratio"), 36.0,
             lambda T: T["stage0"]["candidate"]["i_total"], p2_itot,
             ("$.stage0.candidate", "$.gear_pairs", "$.derived.n_mid", "$.derived.n_out", "$.shafts[1].speed",
              "$.shafts[2].speed", "$.bearings.S2.A.n", "$.bearings.S2.B.n", "$.bearings.S3.A.n", "$.bearings.S3.B.n")),
        ],
    }


def _sign(x):
    return (x > 0) - (x < 0)


def edit_case(family, case, source=None, requirement=None):
    """执行一个编辑用例：编辑 → 重新编译 → 与独立重算比较方向与数值；允许前缀外逐位不变。"""
    name, target, path, value, observe, indep, allowed = case
    src = copy.deepcopy(source if source is not None else load_source(family))
    req = copy.deepcopy(requirement if requirement is not None else load_requirement(family, src))
    T0 = compile_template(src, req)
    src1, req1 = copy.deepcopy(src), copy.deepcopy(req)
    _set(src1 if target == "source" else req1, list(path), copy.deepcopy(value))
    T1 = compile_template(src1, req1)
    o0, o1 = observe(T0), observe(T1)
    i0, i1 = indep(src, req), indep(src1, req1)
    f0, f1 = _flat(T0), _flat(T1)
    changed = sorted(k for k in set(f0) | set(f1) if f0.get(k) != f1.get(k))
    unexpected = [k for k in changed if not any(k == a or k.startswith(a + ".") or k.startswith(a + "[") for a in allowed)]
    stage0_equal = _stage0_common_equal(family, src1, req1, T1)
    ok = (o0 == i0 and o1 == i1 and _sign(o1 - o0) == _sign(i1 - i0) and _sign(o1 - o0) != 0 and not unexpected
          and stage0_equal)
    return {"family": family, "edit": name, "target": target, "observed": [o0, o1], "independent": [i0, i1],
            "direction": _sign(o1 - o0), "changed_paths": changed, "unexpected_changes": unexpected,
            "stage0_common_bitwise_equal": stage0_equal, "ok": ok}


def _stage0_common_equal(family, src, req, T):
    """模板中 Stage0 部分与原 Stage0 求解器（直接调用族模块，不经工作流）结果逐位一致。"""
    if T["stage0"]["candidate"] is None:
        return False
    direct = DIRECT_MODELS[family].run(copy.deepcopy(req["parameters"]))["candidates"]
    return _canon(direct[src["candidate_rank"]["value"] - 1]) == _canon(T["stage0"]["candidate"])


def gate_probe():
    """M36 第 3 条门探针：三旗舰系统级求解状态 + 编辑用例 + Stage0 共同部分逐位一致。只读，不写文件。"""
    out = {"families": {}, "edits": [], "passed": False}
    for fam in FAMILIES:
        try:
            src = load_source(fam)
            req = load_requirement(fam, src)
            r = solve(src, req)
        except (OSError, ValueError, KeyError) as e:
            out["families"][fam] = {"system_status": "error", "error": str(e)}
            continue
        T = r["template"]
        out["families"][fam] = {
            "system_status": r["system_status"], "template_status": T["status"],
            "stage0_common_bitwise_equal": _stage0_common_equal(fam, src, req, T),
            "scope_status": {**{s: r["checks"][s]["status"] for s in SYSTEM_SCOPES},
                             **{f"gear_rating.{k}": v["status"] for k, v in r["gear_rating"].items()}},
            "template_missing": len(T["missing"]) + len(T["missing_structural"]),
            "unsupported": [u["component"] for u in T["unsupported"]]}
        for case in _edits()[fam]:
            out["edits"].append(edit_case(fam, case, src, req))
    fams = out["families"].values()
    out["edits_ok"] = bool(out["edits"]) and all(e["ok"] for e in out["edits"]) \
        and all(sum(1 for e in out["edits"] if e["family"] == f) >= 2 for f in FAMILIES)
    out["stage0_ok"] = all(f.get("stage0_common_bitwise_equal") for f in fams)
    out["system_solved"] = all(f.get("system_status") == "solved" for f in fams)
    out["passed"] = out["edits_ok"] and out["stage0_ok"] and out["system_solved"]
    return out
