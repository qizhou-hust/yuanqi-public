"""数值方法（FEA、LTCA、BEM 等）作为"工具"接入数学基座的统一接口。

数值方法不直接给出"合格/不合格"。它输出带"数值收敛记录"的数，作为证据进入公式图：
  - 标定：例如用 FE 标定 YF、单齿刚度 c'、KHβ 中的载荷分布；
  - 复核：与公式结果对比，偏差进入报告。
没有通过数值收敛检查的结果，不能进入公式图。

注意："数值收敛"只说明逐级加密后数值趋于稳定，并给出离散误差估计；
它不说明模型（边界条件、材料、接触假设）正确，也不等于证据等级。
三者分开报告：evidence_level（来自公式注册表）、optimality（KKT，仅优化结果）、solver_convergence（这里）。
字段名 certificate 为兼容旧接口保留，内容即 solver_convergence 记录。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class MethodResult:
    value: float
    unit: str
    certificate: dict      # 兼容旧名；等同于 convergence

    @property
    def convergence(self):
        return self.certificate

    @property
    def assurance(self):
        """与优化器同结构的分项记录；三项互不合并。"""
        return {"schema": "gearmath.assurance/v1",
                "solver_convergence": self.certificate,
                "optimality": [{"status": "not_checked", "reason": "数值方法输出，不是优化结果"}],
                "evidence_level": {"value": "not_assessed", "source": "formula_registry", "scale": "E0–E6",
                                   "note": "数值收敛不提升证据等级；等级由注册表按方法与验证记录给出"}}


@dataclass(frozen=True)
class NumericalMethod:
    id: str
    output: str
    unit: str
    run: Callable[[dict, int], float]   # (输入, 加密级别) -> 数值
    order: float = 2.0                  # 理论收敛阶，用于 Richardson 外推


def converged(method: NumericalMethod, inputs: dict, *, levels=(1, 2, 3), rel_tol=0.05):
    """逐级加密，检查最后两级相对变化 < rel_tol，并用 Richardson 外推估计离散误差。

    返回的记录只描述"数值收敛"（mesh / level convergence），不描述正确性。
    """
    vals = [method.run(inputs, lv) for lv in levels]
    changes = [abs(vals[i + 1] - vals[i]) / abs(vals[i + 1]) for i in range(len(vals) - 1)]
    r = 2.0 ** method.order
    extrapolated = vals[-1] + (vals[-1] - vals[-2]) / (r - 1)
    ok = changes[-1] < rel_tol
    cert = {"property": "numerical_convergence", "kind": "level_refinement",
            "status": "converged" if ok else "not_converged",
            "method": method.id, "levels": list(levels), "values": vals, "relative_changes": changes,
            "assumed_order": method.order,
            "richardson_estimate": extrapolated, "discretization_error_estimate": abs(extrapolated - vals[-1]),
            "accepted": ok, "rule": f"最后两级相对变化 < {rel_tol}",
            "meaning": "数值收敛：只说明加密后数值稳定并估计离散误差；不表示模型正确，也不是证据等级"}
    if not ok:
        raise ArithmeticError(f"{method.id} 数值未收敛：{cert}")
    return MethodResult(vals[-1], method.unit, cert)
