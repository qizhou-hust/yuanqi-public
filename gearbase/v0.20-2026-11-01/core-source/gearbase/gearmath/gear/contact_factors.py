"""Explicit ISO 6336-2:2019 6.3 contact-factor methods (eps_alpha <= 2).

Checked against source PDF 24 / printed 16, equations (19)..(23), Table 3.
Method choice carries the modification/3D-analysis claim; it has no default.
The high transverse contact-ratio method in 6.4 is deliberately unsupported.
"""
from __future__ import annotations

from ..kernel.expr import FormulaError
from ..kernel.graph import Formula, InputSpec, Model
from .inputs import input_specs
from .surface_factors import SOURCE_SHA256

F, S = Formula, InputSpec
SOURCE_STATUS = {
    "iso_equation_images": "verified", "source_sha256": SOURCE_SHA256,
    "source_path": "standards/core/ISO 6336-2-2019.pdf", "pdf_pages": [23, 24, 25],
    "printed_pages": [15, 16, 17], "equations": [17, 18, 19, 20, 21, 22, 23],
    "status": "verified_selected_branch", "unsupported": ["6.4 eps_alpha > 2", "undercut shortening active path"],
}

_DOMAIN = ("eps_alpha > 1", "eps_alpha <= 2", "contact_path_not_shortened >= 1", "contact_path_not_shortened <= 1")
_METHOD_DOMAIN = ("zCa_method_supported >= 1", "zCa_method_supported <= 1")
_NOTE = "ISO 原图已核 PDF24/印刷16；源SHA256=" + SOURCE_SHA256

ZBD_VARIANTS = {
    "spur": [
        F("contact.Z_B.spur", "Z_B", "1", "max(1, M_1)",
          "ISO 6336-2:2019 6.3a 直齿单对齿接触系数（PDF24/印刷16）",
          (*_DOMAIN, "eps_beta <= 0"), note=_NOTE),
        F("contact.Z_D.spur", "Z_D", "1", "max(1, M_2)",
          "ISO 6336-2:2019 6.3a 直齿单对齿接触系数（PDF24/印刷16）",
          (*_DOMAIN, "eps_beta <= 0"), note=_NOTE),
    ],
}
_METHOD_FACTORS = {"helical_3d": 1.0, "helical_manufacturer": 1.07, "helical_unmodified": 1.2}
for _method, _value in _METHOD_FACTORS.items():
    _rows = [F("contact.f_ZCa." + _method, "f_ZCa", "1", repr(_value),
               "ISO 6336-2:2019 6.3b 表3 修形/载荷分布方法（PDF24/印刷16）",
               (*_METHOD_DOMAIN, *_DOMAIN, "eps_beta > 0"), note=_NOTE)]
    for _i, _name, _eqs in ((1, "Z_B", "19–21"), (2, "Z_D", "19、22、23")):
        _rows.append(F("contact." + _name + "." + _method, _name, "1",
                       f"where(eps_beta >= 1, sqrt(f_ZCa), max(1, M_{_i}) + eps_beta*(sqrt(f_ZCa) - max(1, M_{_i})))",
                       f"ISO 6336-2:2019 6.3b/c 式({_eqs})（PDF24/印刷16）",
                       (*_DOMAIN, "eps_beta > 0"), note=_NOTE))
    ZBD_VARIANTS[_method] = _rows

ZBD_INPUTS = [
    S("M_1", "1", "小轮接触点曲率辅助量；式17，不支持根切缩短接触线", ("M_1 > 0",)),
    S("M_2", "1", "大轮接触点曲率辅助量；式18，不支持根切缩短接触线", ("M_2 > 0",)),
    S("eps_alpha", "1", "端面重合度", ("eps_alpha > 0",)),
    S("eps_beta", "1", "纵向重合度", ("eps_beta >= 0",)),
    S("contact_path_not_shortened", "1", "明确确认无根切导致有效啮合线缩短（式17/18前提）",
      ("contact_path_not_shortened >= 1", "contact_path_not_shortened <= 1")),
    S("zCa_method_supported", "1", "明确修形/3D计算证据支持所选表3方法",
      _METHOD_DOMAIN),
]


def standalone_model(method):
    if method not in ZBD_VARIANTS:
        raise FormulaError(f"接触系数方法未实现：{method!r}；可选：{sorted(ZBD_VARIANTS)}")
    fs = ZBD_VARIANTS[method]
    m = Model(fs, inputs=input_specs(fs, ZBD_INPUTS), editions={"ISO 6336-2": "2019"})
    m.selectors = {"method.Z_BD": method}
    return m


def set_contact_method_evidence(model, method, source):
    """Record a real applicability claim. Never silently assign f_ZCa=1."""
    if method not in ZBD_VARIANTS or not isinstance(source, str) or not source.strip():
        raise FormulaError("接触系数需明确支持的方法及非空适用性来源")
    selected = model.selectors.get("method.Z_BD")
    if selected is not None and selected != method:
        raise FormulaError(f"接触证据方法 {method!r} 与已编译方法 {selected!r} 不一致")
    if "zCa_method_supported" in model.specs:
        model.set("zCa_method_supported", 1, "1", "evidence", source)
    model.selector_sources["method.Z_BD"] = source
    return model
