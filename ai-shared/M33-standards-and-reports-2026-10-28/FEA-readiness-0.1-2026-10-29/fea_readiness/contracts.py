from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

STATUSES = {"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"}

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def finite(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)

def vector(values, name):
    if not isinstance(values, (list,tuple)) or len(values)!=3:
        raise ValueError(f"{name} must have three components")
    return [finite(v,name) for v in values]

def rule(id, status, message, measured=None, limit=None, unit=None, required=True, evidence=None):
    if status not in STATUSES: raise ValueError(status)
    return {"check_id":id,"status":status,"required":required,"message":message,
            "measured":measured,"limit":limit,"unit":unit,"evidence":evidence or []}

def eligible(rules):
    required=[r for r in rules if r["required"]]
    return bool(required) and all(r["status"]=="PASS" for r in required)

def load_json(path):
    def reject(value):raise ValueError(f"Non-finite JSON literal: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),parse_constant=reject)

def write_json(path, data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf8")

def cross(a,b):
    return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]

def resultant(loads, origin):
    origin=vector(origin,"moment_origin_mm");force=[0.,0.,0.];moment=[0.,0.,0.]
    for load in loads:
        f=vector(load["force_N"],"force_N");p=vector(load["point_mm"],"point_mm")
        m=cross([p[i]-origin[i] for i in range(3)],f)
        couple=vector(load.get("couple_Nmm",[0,0,0]),"couple_Nmm")
        force=[force[i]+f[i] for i in range(3)];moment=[moment[i]+m[i]+couple[i] for i in range(3)]
    return {"force_N":force,"moment_Nmm":moment,"origin_mm":origin}
