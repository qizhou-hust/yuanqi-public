import re, json, hashlib
from pathlib import Path
p=Path('../v017-system-run/fea-prepare')
s=(p/'L0_patch_CPE6_h0.dat').read_text()
sections={}
for label in ('stresses (elem, integ.pnt.', 'global coordinates (elem, integ.pnt.'):
    block=s.split(label,1)[1].split('\n\n',2)[1]
    pairs=[tuple(map(int,m)) for m in re.findall(r'^\s*(\d+)\s+(\d+)\s+[-+\d.E]+',block,re.M)]
    groups={str(e):sorted(i for el,i in pairs if el==e) for e in sorted({e for e,_ in pairs})}
    assert groups and all(v==list(range(1,10)) for v in groups.values())
    sections[label]={'elements':len(groups),'ip_keys_per_element':list(range(1,10))}
def sha(name): return hashlib.sha256((p/name).read_bytes()).hexdigest()
r={'solver_version':'2.23','solver_sha256':'31be21fc2f0902bd9a05acc2651dbac6dc2a2573dabbf235e39a38cb6f458862','input_sha256':sha('L0_patch_CPE6_h0.inp'),'dat_sha256':sha('L0_patch_CPE6_h0.dat'),'sta_sha256':sha('L0_patch_CPE6_h0.sta'),'observed':sections,'scope':'synthetic linear elastic CPE6 stress and COORD only; no gear-contact validation'}
(p/'ip_probe.json').write_text(json.dumps(r,indent=2))
print(json.dumps(r))
