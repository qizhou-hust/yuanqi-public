import math
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from gearmath.gear.beam_face import face_components
from gearmath.system import shaft_beam as beam, shaft_line as line
from gearmath.system._base import SystemCalcError


class FaceBridge(unittest.TestCase):
    def test_closed_form_and_domain(self):
        E, D, L, P = 206000., 40., 300., 1000.
        m = beam.solve_beam(supports=[dict(name='A', x=0), dict(name='B', x=L)], axial_support='A',
            loads=[line.point_load(name='p', x=L/2, y=0, z=0, F=(0,P,0), C=(0,0,0))],
            segments=[dict(x0=0,x1=L,d=D,d_i=0)], E=E, G=80000,
            shear_model='euler_bernoulli', shear_factor=None, eval_points=[50])
        args = dict(model=m, x0=40, x1=60, direction_deg=60, torsion_delta_mm=-0.002,
                    torsion_source='independent signed example',
                    omitted_effects=('gear_body','housing','bearing_compliance','wheel'))
        result = face_components(**args)
        I = math.pi * D**4 / 64
        slope = P * (3 * L**2 - 12 * 50**2) / (48 * E * I)
        self.assertAlmostEqual(result['bending_delta_mm'], 20 * slope * 0.5, places=13)
        self.assertAlmostEqual(result['signed_shaft_delta_mm'], 20 * slope * 0.5 - 0.002, places=13)
        for changes in (dict(x0=-1), dict(x1=float('inf')), dict(x0=40,x1=61),
                        dict(torsion_delta_mm=None), dict(torsion_source=''),
                        dict(omitted_effects=()), dict(model={**m,'shear_model':'timoshenko'})):
            with self.subTest(changes=changes), self.assertRaises(SystemCalcError):
                face_components(**{**args, **changes})

if __name__ == '__main__': unittest.main()

