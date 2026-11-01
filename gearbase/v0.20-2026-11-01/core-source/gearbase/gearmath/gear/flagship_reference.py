"""Independent L2 reference for H2 edit probes; no production helper imports.

Deliberate reference equations, separately exercised by corruption tests. The
nominal Stage0 center-distance model implies working diameter equals reference
diameter. This does not supply missing system engineering parameters.
"""
import math


def h2_output_tangential_force(*, torque_nmm, module_mm, tooth_count, helix_deg):
    diameter = module_mm * tooth_count / math.cos(math.radians(helix_deg))
    return 2 * torque_nmm / diameter
