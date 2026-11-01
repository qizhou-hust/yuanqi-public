"""Stdlib-only source binding, real SVG geometry and fail-closed preparation checks."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from gearmath.tools import m35_packet as M


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.raw = (M.ROOT/M.SOURCE).read_bytes()
        self.case = json.loads(self.raw)

    def test_real_shifted_source_dimensions_and_svg(self):
        t = M.parameter_table(self.raw)
        p = t['parameters']
        self.assertGreater(p['x_1']['value'], 0)
        self.assertEqual(p['DIN3961_grade_1']['value'], 6)
        self.assertNotIn('A1328_1', p)
        c = self.case['com']
        for i in (1, 2):
            self.assertAlmostEqual(p[f'd_{i}']['value'], c['ZS.Geo.mn']*c[f'ZR[{i-1}].z']/math.cos(c['ZS.Geo.beta']))
            self.assertEqual(p[f'da_{i}']['value'], c[f'ZR[{i-1}].da.nul'])
        svg = ET.fromstring(M.drawing(t))
        circles = svg.findall('{http://www.w3.org/2000/svg}circle')
        self.assertEqual(len(circles), 8)
        for circle, n in zip(circles, [f'{n}_{i}' for i in (1,2) for n in ('da','d','db','df')]):
            self.assertAlmostEqual(float(circle.attrib['r'])*2, p[n]['value'], places=8)
        self.assertIn('NOT FOR MANUFACTURE', M.drawing(t).decode())
        self.assertIn('hand TBD', M.drawing(t).decode())

    def test_svg_has_inline_presentation_without_stylesheet_dependency(self):
        svg = ET.fromstring(M.drawing(M.parameter_table(self.raw)))
        self.assertFalse(svg.findall('{http://www.w3.org/2000/svg}style'))
        for element in svg:
            tag = element.tag.rsplit('}', 1)[-1]
            if tag in ('circle', 'rect', 'path', 'line', 'text'):
                self.assertTrue({'fill', 'stroke', 'stroke-width'} <= set(element.attrib), tag)
            if tag == 'text':
                self.assertIn('font-family', element.attrib)
                self.assertIn(element.attrib['font-size'], ('3', '5'))
                self.assertNotIn('style', element.attrib)
            elif tag in ('circle', 'path'):
                self.assertEqual(element.attrib['fill'], 'none')
        self.assertEqual(len([e for e in svg if 'stroke-dasharray' in e.attrib]), 6)

    def test_invalid_source_and_units_block(self):
        for mutate in (
            lambda c: c.update(id='K01-spur'),
            lambda c: c['report']['A_sn_e_1'].update(unit='um'),
            lambda c: c['report']['Q_grade_1'].update(label='[Q-ISO 1328:2013]'),
            lambda c: c['com'].update({'ZS.Geo.mn': 2.0}),
            lambda c: c['com'].update({'ZS.Geo.beta': 0}),
            lambda c: c['com'].update({'ZR[0].x.nul': 0, 'ZR[1].x.nul': 0}),
        ):
            case = copy.deepcopy(self.case)
            mutate(case)
            with self.assertRaises(ValueError):
                M.parameter_table(M.encoded(case))

    def test_packet_roundtrip_deterministic_unsigned(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(M.generate(d)['packet_integrity_verified'])
            before = {p.name:p.read_bytes() for p in Path(d).iterdir()}
            M.generate(d)
            self.assertEqual(before, {p.name:p.read_bytes() for p in Path(d).iterdir()})
            form = json.loads((Path(d)/'external-review-unsigned.json').read_bytes())
            self.assertIsNone(form['signature'])
            self.assertFalse(M.verify(d)['external_review_completed'])
            self.assertFalse(M.verify(d)['manufacturing_release'])

    def test_fake_artifact_and_rehashed_manifest_block(self):
        for name in ('source.json', 'parameters.json', 'manufacturing-review.svg', 'external-review-unsigned.json'):
            with tempfile.TemporaryDirectory() as d:
                M.generate(d)
                p = Path(d)/name
                p.write_bytes(p.read_bytes()+b' fake engineer signoff')
                mp = Path(d)/'manifest.json'
                manifest = json.loads(mp.read_bytes())
                for a in manifest['artifacts']:
                    if a['path'] == name:
                        a['sha256'] = M.sha(p.read_bytes())
                mp.write_bytes(M.encoded(manifest))
                with self.assertRaises(ValueError):
                    M.verify(d)

    def test_manifest_order_and_fake_release_block(self):
        for mutate in (lambda m: m['artifacts'].reverse(), lambda m: m.update(manufacturing_release=True),
                       lambda m: m.update(external_review_completed=True)):
            with tempfile.TemporaryDirectory() as d:
                M.generate(d)
                p = Path(d)/'manifest.json'
                manifest = json.loads(p.read_bytes())
                mutate(manifest)
                p.write_bytes(M.encoded(manifest))
                with self.assertRaises(ValueError):
                    M.verify(d)

    def test_missing_extra_and_traversal_artifact_block(self):
        with tempfile.TemporaryDirectory() as d:
            M.generate(d)
            (Path(d)/'unexpected.txt').write_text('extra')
            with self.assertRaises(ValueError):
                M.verify(d)
            (Path(d)/'unexpected.txt').unlink()
            (Path(d)/'manufacturing-review.svg').unlink()
            with self.assertRaises((ValueError, FileNotFoundError)):
                M.verify(d)
        with tempfile.TemporaryDirectory() as d:
            M.generate(d)
            p = Path(d)/'manifest.json'
            manifest = json.loads(p.read_bytes())
            manifest['artifacts'][0]['path'] = '../forged.json'
            p.write_bytes(M.encoded(manifest))
            with self.assertRaises(ValueError):
                M.verify(d)
        with tempfile.TemporaryDirectory() as d:
            M.generate(d)
            p = Path(d)/'external-review-unsigned.json'
            form = json.loads(p.read_bytes())
            form.update(signature='Fake engineer', independent_of_author=True, status='approved')
            p.write_bytes(M.encoded(form))
            with self.assertRaises(ValueError):
                M.verify(d)


if __name__ == '__main__':
    unittest.main()
