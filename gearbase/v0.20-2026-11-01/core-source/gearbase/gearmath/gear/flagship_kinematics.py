"""Physical kinematics shared by flagship template and independent checks."""

def tangential_force(torque, diameter):
    return 2.0 * torque / diameter

def two_stage_input_speed(n_out, z2_second, z1_second, z2_first, z1_first):
    return n_out * (z2_second / z1_second) * (z2_first / z1_first)
