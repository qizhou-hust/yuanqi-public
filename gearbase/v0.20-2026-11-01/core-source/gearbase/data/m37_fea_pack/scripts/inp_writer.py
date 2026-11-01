"""CalculiX .inp 生成与格式自检（不调用 ccx）。

约定：单位 N、mm、MPa；二维平面应变，*SOLID SECTION 第二行为厚度（本包一律 1 mm，载荷即"每毫米齿宽"）。
所有集合名大写、≤ 30 字符；每行 ≤ 132 字符（CalculiX 输入行长度上限）。
"""
from __future__ import annotations

import re

ETYPE = {"T6": "CPE6", "Q8": "CPE8"}
NODES_PER = {"CPE6": 6, "CPE8": 8, "CPE8R": 8, "CPS6": 6, "CPS8": 8}


def _chunks(seq, n=8):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


class Deck:
    def __init__(self, heading):
        self.lines = ["*HEADING", heading[:120]]

    def add(self, *lines):
        self.lines += list(lines)

    def mesh(self, mesh, quad_type="CPE8"):
        """写节点与单元；每个 body 一个 ELSET（按单元类型再分块）。"""
        self.add("*NODE")
        self.lines += [f"{n},{p[0]:.12g},{p[1]:.12g},0" for n, p in sorted(mesh.nodes.items())]
        groups = {}
        for e, (kind, conn, body) in sorted(mesh.elements.items()):
            groups.setdefault((body, kind), []).append((e, conn))
        bodies = {}
        for (body, kind), rows in groups.items():
            et = ETYPE[kind] if kind == "T6" else quad_type
            name = f"{body}_{kind}"
            self.add(f"*ELEMENT,TYPE={et},ELSET={name}")
            self.lines += [f"{e}," + ",".join(map(str, c)) for e, c in rows]
            bodies.setdefault(body, []).append(name)
        for body, names in bodies.items():
            self.add(f"*ELSET,ELSET={body}")
            self.lines += [",".join(ch) for ch in _chunks(names)]
        return list(bodies)

    def nset(self, name, nodes):
        self.add(f"*NSET,NSET={name}")
        self.lines += [",".join(map(str, ch)) for ch in _chunks(sorted(set(nodes)))]

    def elset(self, name, elems):
        self.add(f"*ELSET,ELSET={name}")
        self.lines += [",".join(map(str, ch)) for ch in _chunks(sorted(set(elems)))]

    def surface(self, name, edges):
        self.add(f"*SURFACE,NAME={name},TYPE=ELEMENT")
        self.lines += [f"{e},S{s}" for e, s, _ in edges]

    def material(self, E, nu, elsets, thickness=1.0, name="STEEL"):
        self.add(f"*MATERIAL,NAME={name}", "*ELASTIC", f"{E:.12g},{nu:.12g}")
        for es in elsets:
            self.add(f"*SOLID SECTION,ELSET={es},MATERIAL={name}", f"{thickness:.12g}")

    def contact(self, slave, master, kind, penalty=None, name="CI1"):
        """kind: 'penalty'（面-面 + 线性压力-过盈） | 'mortar'（TYPE=MORTAR + HARD，CCX 2.2x，实验性）"""
        self.add(f"*SURFACE INTERACTION,NAME={name}")
        if kind == "penalty":
            self.add("*SURFACE BEHAVIOR,PRESSURE-OVERCLOSURE=LINEAR", f"{penalty:.6g}")
            self.add(f"*CONTACT PAIR,INTERACTION={name},TYPE=SURFACE TO SURFACE", f"{slave},{master}")
        elif kind == "mortar":
            self.add("*SURFACE BEHAVIOR,PRESSURE-OVERCLOSURE=HARD")
            self.add(f"*CONTACT PAIR,INTERACTION={name},TYPE=MORTAR", f"{slave},{master}")
        else:
            raise ValueError(kind)

    def boundary(self, rows, op_new=False):
        """rows: (node|NSET, dof1, dof2[, value])"""
        self.add("*BOUNDARY,OP=NEW" if op_new else "*BOUNDARY")
        for r in rows:
            if len(r) == 3:
                self.add(f"{r[0]},{r[1]},{r[2]}")
            else:
                self.add(f"{r[0]},{r[1]},{r[2]},{r[3]:.12g}")

    def equation(self, terms):
        """terms: [(node, dof, coef), ...]，首项为被消去的从自由度。"""
        self.add("*EQUATION", str(len(terms)))
        flat = [f"{n},{d},{c:.15g}" for n, d, c in terms]
        for ch in _chunks(flat, 4):
            self.add(",".join(ch))

    def cload(self, loads, op_new=False):
        """loads: {(node, dof): value}"""
        self.add("*CLOAD,OP=NEW" if op_new else "*CLOAD")
        self.lines += [f"{n},{d},{v:.12g}" for (n, d), v in sorted(loads.items()) if v != 0.0]

    def text(self):
        return "\n".join(self.lines) + "\n"


# ------------------------------------------------------------------ 自检
KNOWN = {"*HEADING", "*NODE", "*ELEMENT", "*NSET", "*ELSET", "*SURFACE", "*MATERIAL", "*ELASTIC",
         "*SOLID SECTION", "*SURFACE INTERACTION", "*SURFACE BEHAVIOR", "*CONTACT PAIR", "*BOUNDARY",
         "*EQUATION", "*STEP", "*STATIC", "*CLOAD", "*NODE PRINT", "*EL PRINT", "*CONTACT PRINT",
         "*CONTACT FILE", "*NODE FILE", "*EL FILE", "*END STEP"}


def _params(line):
    parts = [p.strip() for p in line.split(",")]
    kw = parts[0].upper()
    prm = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            prm[k.strip().upper()] = v.strip().upper()
        elif p:
            prm[p.upper()] = True
    return kw, prm


def lint(text):
    """返回 (errors, stats)。检查：关键字白名单、行长、单元节点数与节点存在、集合/面/材料/相互作用引用一致、
    *STEP 配对、*EQUATION 结构、数据行数值可解析。"""
    errors = []
    lines = text.splitlines()
    nodes, elems = set(), {}
    nsets, elsets, surfs, mats, inters = {}, {}, {}, set(), set()
    refs = []          # (kind, name, lineno)
    cur, prm, eq_left = None, {}, 0
    step_open = 0
    nsteps = 0
    for i, raw in enumerate(lines, 1):
        if len(raw) > 132:
            errors.append(f"L{i}: 行长 {len(raw)} > 132")
        line = raw.strip()
        if not line or line.startswith("**"):
            continue
        if line.startswith("*"):
            cur, prm = _params(line)
            if cur not in KNOWN:
                errors.append(f"L{i}: 未知关键字 {cur}")
            if cur == "*STEP":
                if step_open:
                    errors.append(f"L{i}: *STEP 未关闭又开新步")
                step_open, nsteps = 1, nsteps + 1
            elif cur == "*END STEP":
                if not step_open:
                    errors.append(f"L{i}: 多余的 *END STEP")
                step_open = 0
            elif cur == "*NSET":
                nsets.setdefault(prm.get("NSET"), set())
            elif cur == "*ELSET":
                elsets.setdefault(prm.get("ELSET"), set())
            elif cur == "*ELEMENT":
                if prm.get("TYPE") not in NODES_PER:
                    errors.append(f"L{i}: 不支持的单元类型 {prm.get('TYPE')}")
                if "ELSET" in prm:
                    elsets.setdefault(prm["ELSET"], set())
            elif cur == "*SURFACE":
                surfs[prm.get("NAME")] = []
            elif cur == "*MATERIAL":
                mats.add(prm.get("NAME"))
            elif cur == "*SURFACE INTERACTION":
                inters.add(prm.get("NAME"))
            elif cur == "*SOLID SECTION":
                refs += [("elset", prm.get("ELSET"), i), ("material", prm.get("MATERIAL"), i)]
            elif cur == "*CONTACT PAIR":
                refs.append(("interaction", prm.get("INTERACTION"), i))
                if prm.get("TYPE") not in ("SURFACE TO SURFACE", "NODE TO SURFACE", "MORTAR", "LINMORTAR"):
                    errors.append(f"L{i}: 接触类型 {prm.get('TYPE')}")
            elif cur == "*CONTACT PRINT" and "SLAVE" in prm:
                refs += [("surface", prm["SLAVE"], i), ("surface", prm.get("MASTER"), i)]
            elif cur in ("*NODE PRINT", "*NODE FILE") and "NSET" in prm:
                refs.append(("nset", prm["NSET"], i))
            elif cur in ("*EL PRINT", "*EL FILE") and "ELSET" in prm:
                refs.append(("elset", prm["ELSET"], i))
            elif cur in ("*STATIC", "*BOUNDARY", "*CLOAD", "*NODE PRINT", "*EL PRINT", "*CONTACT PRINT") and not step_open \
                    and cur not in ("*BOUNDARY",):
                errors.append(f"L{i}: {cur} 位于 *STEP 之外")
            if cur == "*EQUATION":
                eq_left = -1
            continue
        f = [x.strip() for x in line.split(",") if x.strip() != ""]
        try:
            if cur == "*NODE":
                nodes.add(int(f[0])); [float(v) for v in f[1:]]
            elif cur == "*ELEMENT":
                e = int(f[0]); conn = [int(v) for v in f[1:]]
                if len(conn) != NODES_PER.get(prm.get("TYPE"), len(conn)):
                    errors.append(f"L{i}: 单元 {e} 节点数 {len(conn)}")
                if e in elems:
                    errors.append(f"L{i}: 单元号重复 {e}")
                elems[e] = conn
                if "ELSET" in prm:
                    elsets[prm["ELSET"]].add(e)
            elif cur == "*NSET":
                for v in f:
                    if v.lstrip("-").isdigit():
                        nsets[prm["NSET"]].add(int(v))
                    else:
                        refs.append(("nset", v.upper(), i)); nsets[prm["NSET"]] |= nsets.get(v.upper(), set())
            elif cur == "*ELSET":
                for v in f:
                    if v.lstrip("-").isdigit():
                        elsets[prm["ELSET"]].add(int(v))
                    else:
                        refs.append(("elset", v.upper(), i)); elsets[prm["ELSET"]] |= elsets.get(v.upper(), set())
            elif cur == "*SURFACE":
                e, s = int(f[0]), f[1].upper()
                if e not in elems:
                    errors.append(f"L{i}: 面引用未定义单元 {e}")
                else:
                    nside = 3 if len(elems[e]) == 6 else 4
                    if not re.fullmatch(r"S[1-4]", s) or int(s[1]) > nside:
                        errors.append(f"L{i}: 非法边号 {s}（单元 {e}）")
                surfs[prm["NAME"]].append((e, s))
            elif cur == "*CONTACT PAIR":
                refs += [("surface", f[0].upper(), i), ("surface", f[1].upper(), i)]
            elif cur in ("*BOUNDARY", "*CLOAD"):
                tgt = f[0]
                if tgt.isdigit():
                    if int(tgt) not in nodes:
                        errors.append(f"L{i}: {cur} 引用未定义节点 {tgt}")
                else:
                    refs.append(("nset", tgt.upper(), i))
                d1 = int(f[1])
                if not 1 <= d1 <= 6:
                    errors.append(f"L{i}: 自由度 {d1}")
                [float(v) for v in f[2:]]
            elif cur == "*EQUATION":
                if eq_left == -1:
                    eq_left = int(f[0])
                    if eq_left < 2:
                        errors.append(f"L{i}: *EQUATION 项数 {eq_left}")
                else:
                    if len(f) % 3:
                        errors.append(f"L{i}: *EQUATION 数据行字段数 {len(f)}")
                    for k in range(0, len(f), 3):
                        if int(f[k]) not in nodes:
                            errors.append(f"L{i}: *EQUATION 引用未定义节点 {f[k]}")
                        float(f[k + 2])
                    eq_left -= len(f) // 3
            elif cur == "*STATIC":
                [float(v) for v in f]
        except (ValueError, IndexError) as ex:
            errors.append(f"L{i}: 数据行无法解析（{cur}）：{ex}")
    if step_open:
        errors.append("最后一个 *STEP 未关闭")
    for e, conn in elems.items():
        for n in conn:
            if n not in nodes:
                errors.append(f"单元 {e} 引用未定义节点 {n}")
                break
    table = {"nset": nsets, "elset": elsets, "surface": surfs, "material": mats, "interaction": inters}
    for kind, name, ln in refs:
        if name is None or name not in table[kind]:
            errors.append(f"L{ln}: 引用了未定义的 {kind} {name}")
    for nm, s in nsets.items():
        bad = [n for n in s if n not in nodes]
        if bad:
            errors.append(f"NSET {nm} 含未定义节点 {bad[:3]}")
    for nm, s in surfs.items():
        if not s:
            errors.append(f"面 {nm} 为空")
    for nm, s in nsets.items():
        if not s:
            errors.append(f"NSET {nm} 为空")
    if nsteps == 0:
        errors.append("没有 *STEP")
    stats = {"nodes": len(nodes), "elements": len(elems), "nsets": len(nsets), "elsets": len(elsets),
             "surfaces": len(surfs), "steps": nsteps, "lines": len(lines)}
    return errors, stats
