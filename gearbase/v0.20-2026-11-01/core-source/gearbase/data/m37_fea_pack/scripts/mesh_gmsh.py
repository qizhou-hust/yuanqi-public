"""用 gmsh Python API 生成二维二次单元网格（CPE6 三角形 / CPE8 四边形），并做单元质量检查。

只依赖 gmsh（pip install gmsh==4.15.2 或 4.11–4.15）。不读写任何 CAD 文件：边界由 gear_geom 的解析点列给出。
单元节点顺序转换为 CalculiX 约定并保证逆时针（正面积）；边号：
  CPE6：S1=(1,2) S2=(2,3) S3=(3,1)；CPE8：S1=(1,2) S2=(2,3) S3=(3,4) S4=(4,1)。
"""
from __future__ import annotations

import math

TRI_SIDES = ((0, 1, 3), (1, 2, 4), (2, 0, 5))
QUAD_SIDES = ((0, 1, 4), (1, 2, 5), (2, 3, 6), (3, 0, 7))


class Mesh:
    def __init__(self):
        self.nodes = {}            # tag -> (x, y)
        self.elements = {}         # eid -> (kind 'T6'|'Q8', [nodes], body)
        self.edges = {}            # 边界曲线名 -> [(eid, side, (n1, n2, nmid))]
        self.quality = {}
        self.gmsh_version = ""

    def count(self):
        out = {}
        for k, _, _ in self.elements.values():
            out[k] = out.get(k, 0) + 1
        return out

    def body_nodes(self, body):
        return sorted({n for k, c, b in self.elements.values() if b == body for n in c})

    def edge_nodes(self, *names):
        return sorted({n for nm in names for _, _, row in self.edges.get(nm, []) for n in row})


def _signed_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return a / 2


def mesh_2d(surfaces, fields, h_max, *, quads=False, order=2, optimize_ho=None, msh_path=None, verbose=False):
    """surfaces：[{name, outer:[piece...], holes:[[piece...]...]}]；piece = {kind:'line'|'arc'|'spline', pts, center?, name}
    相邻 piece 首尾点必须完全相同（按 1e-9 mm 合并）。
    fields：[{kind:'curve', curves:[name...], h_min, d_min, d_max}] 或 [{kind:'disk', center:(x,y), r_in, h_in, r_out}]
    返回 Mesh。"""
    import gmsh
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1 if verbose else 0)
        gmsh.model.add("m37")
        geo = gmsh.model.geo
        pcache = {}
        sidx = [0]

        def pt(p):
            key = (sidx[0], round(p[0], 9), round(p[1], 9))   # 每个面独立：不同物体不共享节点
            if key not in pcache:
                pcache[key] = geo.addPoint(p[0], p[1], 0.0)
            return pcache[key]

        curve_names = {}
        transfinite = []

        def build_loop(pieces):
            tags = []
            for pc in pieces:
                kind, pts = pc["kind"], pc["pts"]
                if kind == "line":
                    t = [geo.addLine(pt(pts[0]), pt(pts[-1]))]
                elif kind == "spline":
                    ids = [pt(pts[0])] + [geo.addPoint(p[0], p[1], 0.0) for p in pts[1:-1]] + [pt(pts[-1])]
                    t = [geo.addSpline(ids)]
                elif kind == "arc":
                    c = pc["center"]
                    a0 = math.atan2(pts[0][1] - c[1], pts[0][0] - c[0])
                    a1 = math.atan2(pts[-1][1] - c[1], pts[-1][0] - c[0])
                    R = math.dist(pts[0], c)
                    if abs(R - math.dist(pts[-1], c)) > 1e-7 * max(1, R):
                        raise ValueError(f"圆弧 {pc.get('name')} 端点半径不一致")
                    d = a1 - a0
                    sign = pc.get("ccw")
                    if sign is True and d < 0:
                        d += 2 * math.pi
                    elif sign is False and d > 0:
                        d -= 2 * math.pi
                    elif sign is None:
                        d = (d + math.pi) % (2 * math.pi) - math.pi
                    nseg = max(1, int(math.ceil(abs(d) / (math.pi / 2))))
                    ctag = geo.addPoint(c[0], c[1], 0.0)
                    prev = pts[0]
                    t = []
                    for k in range(1, nseg + 1):
                        q = pts[-1] if k == nseg else (c[0] + R * math.cos(a0 + d * k / nseg), c[1] + R * math.sin(a0 + d * k / nseg))
                        t.append(geo.addCircleArc(pt(prev), ctag, pt(q)))
                        prev = q
                else:
                    raise ValueError(kind)
                for x in t:
                    curve_names[x] = pc["name"]
                if pc.get("n_nodes"):
                    for x in t:
                        transfinite.append((x, int(pc["n_nodes"])))
                tags += t
            return geo.addCurveLoop(tags)

        surf_tags = []
        for si, s in enumerate(surfaces):
            sidx[0] = si
            loops = [build_loop(s["outer"])] + [build_loop(h) for h in s.get("holes", [])]
            surf_tags.append((geo.addPlaneSurface(loops), s["name"]))
        for ctag, nn in transfinite:
            geo.mesh.setTransfiniteCurve(ctag, nn)
        geo.synchronize()

        by_name = {}
        for t, nm in curve_names.items():
            by_name.setdefault(nm, []).append(t)
        fids = []
        for f in fields:
            if f["kind"] == "curve":
                tags = [t for nm in f["curves"] for t in by_name.get(nm, [])]
                if not tags:
                    raise ValueError(f"尺寸场引用了不存在的曲线 {f['curves']}")
                d = gmsh.model.mesh.field.add("Distance")
                gmsh.model.mesh.field.setNumbers(d, "CurvesList", tags)
                gmsh.model.mesh.field.setNumber(d, "Sampling", f.get("sampling", 600))
                th = gmsh.model.mesh.field.add("Threshold")
                gmsh.model.mesh.field.setNumber(th, "InField", d)
                gmsh.model.mesh.field.setNumber(th, "SizeMin", f["h_min"])
                gmsh.model.mesh.field.setNumber(th, "SizeMax", h_max)
                gmsh.model.mesh.field.setNumber(th, "DistMin", f["d_min"])
                gmsh.model.mesh.field.setNumber(th, "DistMax", f["d_max"])
                fids.append(th)
            elif f["kind"] == "disk":
                # 以点为中心：r_in 内为 h_in，线性增长到 r_out 处的 h_max
                d = gmsh.model.mesh.field.add("MathEval")
                cx, cy = f["center"]
                h_in, r_in, r_out = f["h_in"], f["r_in"], f["r_out"]
                rr = f"Sqrt((x-({cx!r}))^2+(y-({cy!r}))^2)"
                expr = f"Min({h_max!r}, {h_in!r} + Max(0, {rr}-{r_in!r})*({h_max!r}-{h_in!r})/({r_out!r}-{r_in!r}))"
                gmsh.model.mesh.field.setString(d, "F", expr)
                fids.append(d)
            else:
                raise ValueError(f["kind"])
        if fids:
            mn = gmsh.model.mesh.field.add("Min")
            gmsh.model.mesh.field.setNumbers(mn, "FieldsList", fids)
            gmsh.model.mesh.field.setAsBackgroundMesh(mn)
        for k, v in {"Mesh.MeshSizeExtendFromBoundary": 0, "Mesh.MeshSizeFromPoints": 0,
                     "Mesh.MeshSizeFromCurvature": 0, "Mesh.MeshSizeMax": h_max,
                     "Mesh.Algorithm": 8 if quads else 6, "Mesh.ElementOrder": order,
                     "Mesh.SecondOrderIncomplete": 1, "Mesh.RecombineAll": 1 if quads else 0,
                     "Mesh.RecombinationAlgorithm": 1, "Mesh.Smoothing": 5}.items():
            gmsh.option.setNumber(k, v)
        if optimize_ho is None:
            optimize_ho = not quads      # 四边形重组后的高阶优化在 gmsh 4.15 中可能失败；本包四边形只用于直边补丁检验
        if optimize_ho and order == 2:
            gmsh.option.setNumber("Mesh.HighOrderOptimize", 2)
            gmsh.option.setNumber("Mesh.HighOrderThresholdMin", 0.5)   # 对缩放雅可比 <0.5 的曲边单元做高阶优化
        gmsh.model.mesh.generate(2)
        if msh_path:
            gmsh.write(str(msh_path))
        M = Mesh()
        M.gmsh_version = gmsh.option.getString("General.Version")
        ntags, xyz, _ = gmsh.model.mesh.getNodes()
        for i, t in enumerate(ntags):
            M.nodes[int(t)] = (float(xyz[3 * i]), float(xyz[3 * i + 1]))
        # 2D 单元
        eid = 0
        qual_tags, gmsh_to_eid = [], {}
        for stag, sname in surf_tags:
            types, etags, enodes = gmsh.model.mesh.getElements(2, stag)
            for ty, tg, nd in zip(types, etags, enodes):
                name, _, _, nn, _, _ = gmsh.model.mesh.getElementProperties(ty)
                if ty == 9:
                    kind, nper = "T6", 6
                elif ty == 16:
                    kind, nper = "Q8", 8
                else:
                    raise RuntimeError(f"意外的单元类型 {name}（需要二次三角形 9 或 8 节点四边形 16）")
                for j, g in enumerate(tg):
                    conn = [int(n) for n in nd[j * nper:(j + 1) * nper]]
                    corners = [M.nodes[n] for n in conn[:3 if kind == 'T6' else 4]]
                    if _signed_area(corners) < 0:
                        conn = ([conn[0], conn[2], conn[1], conn[5], conn[4], conn[3]] if kind == "T6"
                                else [conn[0], conn[3], conn[2], conn[1], conn[7], conn[6], conn[5], conn[4]])
                    eid += 1
                    M.elements[eid] = (kind, conn, sname)
                    qual_tags.append(int(g))
                    gmsh_to_eid[int(g)] = eid
        used = {n for _, c, _ in M.elements.values() for n in c}
        M.nodes = {n: p for n, p in M.nodes.items() if n in used}     # 去掉圆心等孤立几何点
        q = gmsh.model.mesh.getElementQualities(qual_tags, "minSJ")
        qs = sorted(float(v) for v in q)
        gq = sorted(float(v) for v in gmsh.model.mesh.getElementQualities(qual_tags, "gamma"))
        M.quality = {"minSJ": {"meaning": "gmsh 缩放雅可比最小值（二次单元、含曲边；>0 即无翻转，验收 >0.3）",
                               "min": qs[0], "p01": qs[max(0, len(qs) // 100 - 1)], "median": qs[len(qs) // 2],
                               "n_below_0.3": sum(1 for v in qs if v < 0.3), "n_nonpositive": sum(1 for v in qs if v <= 0)},
                     "gamma": {"meaning": "gmsh 形状质量（内切/外接半径比，1=正三角形；四边形按 gmsh 定义）",
                               "min": gq[0], "p01": gq[max(0, len(gq) // 100 - 1)], "median": gq[len(gq) // 2],
                               "n_below_0.2": sum(1 for v in gq if v < 0.2)},
                     "n": len(qs), "min": qs[0]}
        # 边界边：按曲线名
        side_of = {}
        for e, (kind, conn, _) in M.elements.items():
            for s, idx in enumerate(TRI_SIDES if kind == "T6" else QUAD_SIDES, 1):
                key = frozenset((conn[idx[0]], conn[idx[1]]))
                side_of.setdefault(key, []).append((e, s, (conn[idx[0]], conn[idx[1]], conn[idx[2]])))
        for ctag, nm in curve_names.items():
            types, etags, enodes = gmsh.model.mesh.getElements(1, ctag)
            for ty, tg, nd in zip(types, etags, enodes):
                if ty != 8:
                    raise RuntimeError("边界不是 3 节点线单元")
                for j in range(len(tg)):
                    a, b = int(nd[3 * j]), int(nd[3 * j + 1])
                    owners = side_of.get(frozenset((a, b)), [])
                    if len(owners) != 1:
                        raise RuntimeError(f"曲线 {nm} 上的边属于 {len(owners)} 个单元（应为 1）")
                    M.edges.setdefault(nm, []).append(owners[0])
        return M
    finally:
        gmsh.finalize()


def gmsh_version():
    import gmsh
    gmsh.initialize()
    try:
        return gmsh.option.getString("General.Version")
    finally:
        gmsh.finalize()
