"""Transparent analytical estimates, with restricted domains and explicit units.

Hertz implementation follows the same line-contact equations as M37 post.py;
independent tests use its frozen reference values and scaling identities.
No ISO fatigue rating, generated trochoid, or tooth-root strength claim.
"""
import math
from .contracts import finite

def checked(result):
    """Reject overflow/underflow-induced non-finite derived quantities."""
    for k,v in result.items():
        if isinstance(v,(int,float)) and not isinstance(v,bool):finite(v,k)
    return result

def material(E_MPa, nu):
    E=finite(E_MPa,"E_MPa",True);v=finite(nu,"nu")
    if not -1<v<.5:raise ValueError("Isotropic elastic Poisson ratio must lie in (-1, 0.5)")
    return E,v

def hertz_line(q_N_per_mm, R1_mm, R2_mm, E1_MPa, nu1, E2_MPa, nu2):
    q=finite(q_N_per_mm,"q_N_per_mm")
    r1=finite(R1_mm,"R1_mm",True);r2=finite(R2_mm,"R2_mm",True)
    E1,v1=material(E1_MPa,nu1);E2,v2=material(E2_MPa,nu2)
    Es=1/((1-v1*v1)/E1+(1-v2*v2)/E2);R=1/(1/r1+1/r2)
    if q==0:
        return checked({"method":"hertz_line_two_convex_bodies","q_N_per_mm":q,"E_star_MPa":Es,
            "R_eff_mm":R,"half_width_mm":0.,"p0_MPa":0.,"a_over_min_radius":0.,
            "integrated_line_load_N_per_mm":0.,
            "scope":"Zero-load branch; no active Hertz contact pressure is predicted",
            "reference":"M37 post.hertz_line; classical Hertz line contact (see research sources)"})
    a=math.sqrt(4*q*R/(math.pi*Es));p0=2*q/(math.pi*a)
    return checked({"method":"hertz_line_two_convex_bodies","q_N_per_mm":q,"E_star_MPa":Es,
            "R_eff_mm":R,"half_width_mm":a,"p0_MPa":p0,"a_over_min_radius":a/min(r1,r2),
            "integrated_line_load_N_per_mm":math.pi*a*p0/2,
            "scope":"Smooth nonconforming convex cylinders, frictionless elastic small contact patch, plane-strain interior; no edge/plastic/roughness correction",
            "reference":"M37 post.hertz_line; classical Hertz line contact (see research sources)"})

def spur_pair(z1,z2,module_mm,alpha_deg,face_width_mm,torque_Nm,s_mm=0.,addendum_coeff=1.):
    for z in [z1,z2]:
        if isinstance(z,bool) or not isinstance(z,int) or z<3:raise ValueError("Tooth counts must be integers >= 3")
    m=finite(module_mm,"module_mm",True);b=finite(face_width_mm,"face_width_mm",True)
    al=finite(alpha_deg,"alpha_deg");T=finite(torque_Nm,"torque_Nm",True);s=finite(s_mm,"s_mm")
    ha=finite(addendum_coeff,"addendum_coeff",True)
    if not 0<al<45:raise ValueError("Pressure angle outside supported (0,45) degree domain")
    al=math.radians(al);r1=m*z1/2;r2=m*z2/2;rb1=r1*math.cos(al);rb2=r2*math.cos(al)
    ra1=r1+ha*m;ra2=r2+ha*m;pb=math.pi*m*math.cos(al)
    rho1=r1*math.sin(al)+s;rho2=r2*math.sin(al)-s
    start=r2*math.sin(al)-math.sqrt(ra2*ra2-rb2*rb2)
    end=math.sqrt(ra1*ra1-rb1*rb1)-r1*math.sin(al)
    if not start<=s<=end or min(rho1,rho2)<=0:raise ValueError("Contact point outside nominal active involute domain")
    pairs=[k for k in range(math.ceil((start-s)/pb),math.floor((end-s)/pb)+1)]
    Ft=T*1000/r1;Fn=Ft/math.cos(al)
    return checked({"method":"nominal_unshifted_external_spur","r1_mm":r1,"r2_mm":r2,"rb1_mm":rb1,"rb2_mm":rb2,
            "ra1_mm":ra1,"ra2_mm":ra2,"center_distance_mm":r1+r2,"base_pitch_mm":pb,
            "path_start_mm":start,"path_end_mm":end,"contact_ratio":(end-start)/pb,
            "contact_coordinate_mm":s,"nominal_pairs_at_phase":len(pairs),"pair_offsets":pairs,
            "rho1_mm":rho1,"rho2_mm":rho2,"Ft_N":Ft,"Fr_N":Ft*math.tan(al),"Fn_N":Fn,
            "full_load_q_N_per_mm":Fn/b,"torque_per_1mm_Nmm":T*1000/b,
            "rack_undercut_screen_zmin":2*ha/(math.sin(al)**2),
            "undercut_screen":min(z1,z2)<2*ha/(math.sin(al)**2),
            "scope":"Zero profile shift, standard center distance, no tip/root truncation or relief; nominal undercut screen is not generated fillet verification"})

def rectangular_cantilever(force_N,length_mm,width_mm,depth_mm,E_MPa,nu,shear_factor=5/6):
    F=finite(force_N,"force_N",True);L=finite(length_mm,"length_mm",True)
    b=finite(width_mm,"width_mm",True);h=finite(depth_mm,"depth_mm",True)
    E,v=material(E_MPa,nu);k=finite(shear_factor,"shear_factor",True)
    I=b*h**3/12;A=b*h;G=E/(2*(1+v));db=F*L**3/(3*E*I);ds=F*L/(k*G*A)
    return checked({"method":"rectangular_cantilever_tip_force","nominal_root_bending_MPa":6*F*L/(b*h*h),
            "bending_displacement_mm":db,"shear_displacement_mm":ds,"total_displacement_mm":db+ds,
            "stiffness_N_per_mm":F/(db+ds),"length_depth_ratio":L/h,
            "scope":"Uniform rectangular beam, fixed root, transverse end load, linear elastic small deflection; no tooth stress concentration, foundation, rim or contact compliance"})

def precalculate(spec):
    kind=spec["kind"]
    if kind=="hertz_line":return {"contact":hertz_line(**spec["inputs"])}
    if kind=="rectangular_cantilever":return {"beam":rectangular_cantilever(**spec["inputs"])}
    if kind=="nominal_spur":
        g=spur_pair(**spec["inputs"]);mat=spec["material"]
        h=hertz_line(g["full_load_q_N_per_mm"],g["rho1_mm"],g["rho2_mm"],**mat)
        return {"geometry":g,"contact":h,"prediction_role":"single-pair full-load reference; multi-pair pressure requires load sharing"}
    raise ValueError("Unsupported analytical model: "+str(kind))
