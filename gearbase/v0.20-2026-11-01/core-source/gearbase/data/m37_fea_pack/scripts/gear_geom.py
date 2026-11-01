"""外啮合直齿轮端面齿形：由基本齿条（带齿顶圆角 rho_fP）展成，纯 Python、零依赖。

坐标约定（单个轮齿的局部坐标）：
  轮心在原点，被测轮齿中心线沿 +y；极角 theta 从 +y 轴量起，顺时针（朝 +x）为正：
  x = R*sin(theta), y = R*cos(theta)。
  "右齿面" = x > 0 一侧。L3 中两轮的工作齿面都是各自局部坐标下的右齿面。

展成运动（齿条刀具与轮坯纯滚动，滚动线为分度圆 r = z*m/2）：
  刀具基准线在 y = r + x*m；刀具齿（切出齿槽）中心在 u = pi*m/2。
  刀尖圆角中心（刀具坐标）：u_c = pi*m/4 + (hfP-rhofP)*m*tan(alpha) + rho/cos(alpha)，
                            y_c = r + (x - hfP + rhofP)*m，rho = rhofP*m。
  轮坯转角 phi 时，刀具平移 r*phi；刀具坐标点 (u, y) 在轮坯坐标中为 R_ccw(phi)·(u + r*phi, y)。
  包络条件（啮合定律）：接触点法线过瞬心（刀具坐标中的 (-r*phi, r)）。
  过渡曲线 = 刀尖圆角在 phi∈[phi_b, phi_a] 上的包络；渐开线段解析给出。
本模块与 ISO 6336-3 方法 B 的几何假设一致（名义变位、无凸台、无磨削台阶）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def inv(a):
    return math.tan(a) - a


def inv_inverse(v, tol=1e-15):
    """渐开线函数反函数（牛顿法）。"""
    a = (3.0 * v) ** (1.0 / 3.0) if v > 0 else 0.0
    for _ in range(60):
        f = math.tan(a) - a - v
        d = math.tan(a) ** 2
        if d == 0:
            a = 1e-6
            continue
        step = f / d
        a -= step
        if abs(step) < tol:
            break
    return a


@dataclass
class SpurGear:
    z: int
    m: float
    x: float                    # 名义变位系数（用于 ISO 对比）
    alpha_deg: float = 20.0
    haP: float = 1.0
    hfP: float = 1.25
    rhofP: float = 0.38
    x_gen: float | None = None  # 展成用变位（含齿厚减薄）；None = 与 x 相同
    samples_fillet: int = 81
    samples_involute: int = 61
    info: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.x_gen is None:
            self.x_gen = self.x
        a = math.radians(self.alpha_deg)
        self.alpha = a
        self.r = self.z * self.m / 2.0
        self.rb = self.r * math.cos(a)
        self.ra = self.r + (self.haP + self.x) * self.m       # 齿顶按名义变位（与 gearbase da 一致）
        self.rf = self.r + (self.x_gen - self.hfP) * self.m   # 齿根由展成变位决定
        self.rho = self.rhofP * self.m
        self.u_c = math.pi * self.m / 4 + (self.hfP - self.rhofP) * self.m * math.tan(a) + self.rho / math.cos(a)
        self.y_c = self.r + (self.x_gen - self.hfP + self.rhofP) * self.m
        if self.u_c > math.pi * self.m / 2 + 1e-12:
            raise ValueError("rho_fP 过大：刀尖两侧圆角重叠（非法基本齿条）")
        if self.y_c >= self.r:
            raise ValueError("x + rho_fP >= hfP：圆角中心不在滚动线以内，本模块不支持（G>=0）")
        # 分度圆齿厚（展成变位）与半角
        self.s_pitch = self.m * (math.pi / 2 + 2 * self.x_gen * math.tan(a))
        self.psi = self.s_pitch / (2 * self.r)
        self.phi_a = -self.u_c / self.r
        self.phi_b = ((self.y_c - self.r) / math.tan(a) - self.u_c) / self.r
        self._check()

    # ---------- 解析曲线 ----------
    def theta_involute(self, R):
        """右齿面渐开线在半径 R 处的极角（从齿中心线量起）。"""
        aR = math.acos(min(1.0, self.rb / R))
        return self.psi + inv(self.alpha) - inv(aR)

    def fillet_point(self, phi):
        r, rho = self.r, self.rho
        vu, vy = self.u_c + r * phi, self.y_c - r
        n = math.hypot(vu, vy)
        pu, py = self.u_c + rho * vu / n, self.y_c + rho * vy / n
        sx, sy = pu + r * phi, py
        c, s = math.cos(phi), math.sin(phi)
        return (c * sx - s * sy, s * sx + c * sy)

    @staticmethod
    def polar(p):
        return math.hypot(*p), math.atan2(p[0], p[1])

    # ---------- 自检 ----------
    def _check(self):
        pj = self.fillet_point(self.phi_b)
        Rj, tj = self.polar(pj)
        if Rj < self.rb:
            raise ValueError(f"过渡曲线与渐开线连接点 R={Rj:.6f} 低于基圆 {self.rb:.6f}：根切，本题不收录")
        mism = abs(tj - self.theta_involute(Rj))
        if mism > 1e-9 * max(1.0, self.r):
            raise ValueError(f"过渡曲线终点不在渐开线上（{mism:.3e} rad）：通常为根切（连接点接近或低于基圆），本题不收录")
        p0 = self.fillet_point(self.phi_a)
        R0, t0 = self.polar(p0)
        if abs(R0 - self.rf) > 1e-9 * self.r:
            raise ValueError("过渡曲线起点不在齿根圆上")
        # 单调性（无根切）：沿 phi_a -> phi_b 半径单调增加
        prev = -1.0
        for i in range(self.samples_fillet):
            ph = self.phi_a + (self.phi_b - self.phi_a) * i / (self.samples_fillet - 1)
            R, _ = self.polar(self.fillet_point(ph))
            if R < prev - 1e-12:
                raise ValueError("过渡曲线半径非单调：根切")
            prev = R
        sa = 2 * self.ra * self.theta_involute(self.ra)
        if sa < 0.2 * self.m:
            raise ValueError(f"齿顶厚 sa={sa:.3f} < 0.2 m：齿顶过尖，本题不收录")
        self.info.update(rf=self.rf, rb=self.rb, ra=self.ra, r=self.r, R_form=Rj,
                         theta_root_start=t0, theta_form=tj, sa=sa,
                         root_arc=(t0 < math.pi / self.z - 1e-12))

    # ---------- 右侧边界点（从齿槽中心到齿顶） ----------
    def right_side(self):
        """返回 dict：root_arc (theta 起止, R)、fillet 点列（R 增）、involute 点列（R 增）、tip (R, theta)。"""
        fil = [self.fillet_point(self.phi_a + (self.phi_b - self.phi_a) * i / (self.samples_fillet - 1))
               for i in range(self.samples_fillet)]
        Rj = self.info["R_form"]
        inv_pts = []
        n = self.samples_involute
        for i in range(n):
            # 按滚动角均匀取点，近基圆处更密
            tj = math.sqrt(max(0.0, (Rj / self.rb) ** 2 - 1))
            ta = math.sqrt((self.ra / self.rb) ** 2 - 1)
            t = tj + (ta - tj) * i / (n - 1)
            R = self.rb * math.sqrt(1 + t * t)
            th = self.theta_involute(R)
            inv_pts.append((R * math.sin(th), R * math.cos(th)))
        inv_pts[0] = fil[-1]
        return {"root_theta": (math.pi / self.z, self.info["theta_root_start"]), "fillet": fil,
                "involute": inv_pts, "tip_theta": self.theta_involute(self.ra)}

    # ---------- 30° 切线点（ISO 6336-3 危险截面）实测 ----------
    def critical_section_30deg(self):
        """在过渡曲线上找切线与齿中心线成 30° 的点；返回 sFn（弦齿厚，=2x）、rhoF（曲率半径）、点坐标。"""
        def tangent_angle(ph, h=1e-7):
            p1, p2 = self.fillet_point(ph - h), self.fillet_point(ph + h)
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            return math.degrees(math.atan2(abs(dx), abs(dy)))   # 与 y 轴夹角
        lo, hi = self.phi_a, self.phi_b
        # 沿 phi_a->phi_b 夹角从 90° 单调减到 alpha（渐开线起点处）：二分
        fa, fb = tangent_angle(lo + 1e-9 * (hi - lo)) - 30, tangent_angle(hi) - 30
        if fa * fb > 0:
            raise ValueError("过渡曲线上不存在 30° 切线点")
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            fm = tangent_angle(mid) - 30
            if (fm > 0) == (fa > 0):
                lo, fa = mid, fm
            else:
                hi = mid
        ph = 0.5 * (lo + hi)
        p = self.fillet_point(ph)
        # 曲率半径（解析）：过渡曲线是刀尖圆心轨迹（延伸摆线）向外偏置 rho 的曲线，
        # rhoF = rho + rho_c，rho_c = |c'|^3/|c' x c''|，c' ~ (r - y_c, u_c + r*phi)，c'' ~ (-(u_c + r*phi), 2r - y_c)
        r, w = self.r, self.u_c + self.r * ph
        d1 = (r - self.y_c, w)
        d2 = (-w, 2 * r - self.y_c)
        rho = self.rho + math.hypot(*d1) ** 3 / abs(d1[0] * d2[1] - d1[1] * d2[0])
        return {"sFn": 2 * p[0], "rhoF": rho, "point": p, "phi": ph}


def rot(p, ang):
    """绕原点逆时针转 ang（弧度）。"""
    c, s = math.cos(ang), math.sin(ang)
    return (c * p[0] - s * p[1], s * p[0] + c * p[1])


def single_contact_diameter(z1, z2, m, alpha_deg, x1, x2, haP):
    """直齿外啮合（标准中心距之外按无侧隙方程）的 HPSTC 直径 den（小轮 1），与 ISO 6336-3 式一致。"""
    a = math.radians(alpha_deg)
    inv_w = inv(a) + 2 * (x1 + x2) * math.tan(a) / (z1 + z2)
    aw = inv_inverse(inv_w)
    r1, r2 = z1 * m / 2, z2 * m / 2
    rb1, rb2 = r1 * math.cos(a), r2 * math.cos(a)
    ra1, ra2 = r1 + (haP + x1) * m, r2 + (haP + x2) * m
    a_w = (r1 + r2) * math.cos(a) / math.cos(aw)
    pb = math.pi * m * math.cos(a)
    g = math.sqrt(ra1 ** 2 - rb1 ** 2) + math.sqrt(ra2 ** 2 - rb2 ** 2) - a_w * math.sin(aw)
    eps = g / pb
    den1 = 2 * math.sqrt((math.sqrt(ra1 ** 2 - rb1 ** 2) - pb * (eps - 1)) ** 2 + rb1 ** 2)
    return {"den": den1, "eps_alpha": eps, "alpha_w": aw, "a_w": a_w, "pb": pb}


def involute_normal_at(g: SpurGear, R):
    """右齿面渐开线在半径 R 处的点与外法线（单位向量，指向齿外）。"""
    th = g.theta_involute(R)
    p = (R * math.sin(th), R * math.cos(th))
    # 切点：法线与基圆相切；外法线方向 = 渐开线展开方向
    aR = math.acos(g.rb / R)
    # 外法线指向 theta 增大方向且有向外的径向分量（离开齿体）
    ang = th + (math.pi / 2 - aR)   # 从 +y 顺时针；法线与径向夹角 = 90°-alpha_R
    n = (math.sin(ang), math.cos(ang))
    # 校核：n 与齿面切线正交
    h = 1e-6 * R
    th2 = g.theta_involute(R + h)
    p2 = ((R + h) * math.sin(th2), (R + h) * math.cos(th2))
    t = (p2[0] - p[0], p2[1] - p[1])
    tn = math.hypot(*t)
    if abs((t[0] * n[0] + t[1] * n[1]) / tn) > 1e-5:
        raise AssertionError("渐开线法线计算错误")
    return p, n
