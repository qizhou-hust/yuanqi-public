import unittest
from gearmath.tools import bench as B
from gearmath.tools import bench_closure as BC

class TestChineseNumberTrace(unittest.TestCase):
    def test_compound_literal_is_traceable_without_fragment_invention(self):
        self.assertIn(10000., B.input_numbers('功率一万千瓦'))
        self.assertIn(999., B.input_numbers('功率九百九十九千瓦'))
        self.assertNotIn(9., B.input_numbers('功率九百九十九千瓦'))
        for text,value in [('二十',20.),('一百零二',102.),('负一万',-10000.),('零点五',.5)]:
            with self.subTest(text=text):self.assertIn(value,B.input_numbers(text))

    def test_chinese_reply_invention_is_detected(self):
        _,bad=B.check_numbers('功率15kW',{'reply_text':'Recommended power: 九百九十九 kW.'})
        self.assertTrue(bad)
        _,bad=B.check_numbers('功率一万千瓦',{'parsed_requirement':{'power_kW':10000.},'reply_text':'功率一万千瓦。'})
        self.assertEqual(bad,[])

    def test_source_spans_and_unsupported_numerals_fail_closed(self):
        text='功率一万千瓦'
        rows=BC.field_sources(text,{'parsed_requirement':{'power_kW':10000.}})
        source=next(s for s in rows[0]['sources'] if s['kind']=='input_text')
        self.assertEqual(text[slice(*source['span'])],'一万')
        self.assertEqual(source['quote'],'一万')
        _,bad=B.check_numbers('功率15kW',{'reply_text':'建议一百百千瓦'})
        self.assertTrue(bad)

    def test_sign_mixed_magnitude_and_standard_identifiers(self):
        for text,wrong in [('999kW','-九百九十九kW'),('15万小时','10000小时'),('一万亿小时','1000100000000小时'),('ISO/TS6336-20:2022','6336kW')]:
            with self.subTest(text=text):self.assertTrue(B.check_numbers(text,{'reply_text':wrong})[1])
        self.assertEqual(B.input_numbers('15万小时'),[150000.])
        self.assertEqual(B.input_numbers('一万亿小时'),[1e12])
        self.assertEqual(B.input_numbers('-九百九十九kW'),[-999.])
        self.assertEqual(B.input_numbers('DIN7190-1:2017和ISO/TS6336-20:2022'),[])
        for token in ('NaN','Infinity','-inf'):
            self.assertTrue(B.check_numbers('正常功率',{'reply_text':token+' kW'})[1])

    def test_numeric_token_boundaries_do_not_source_subfragments(self):
        for text,value in [('−九百九十九kW',-999.),('负999kW',-999.),('1e3万小时',1e7),('零万小时',0.),('1,000小时',1000.)]:
            with self.subTest(text=text):self.assertEqual(B.input_numbers(text),[value])
        for source,reply in [('−九百九十九kW','999kW'),('负999kW','999kW'),('1e3万小时','10000小时'),('零万小时','10000小时')]:
            with self.subTest(source=source):self.assertTrue(B.check_numbers(source,{'reply_text':reply})[1])
        for token in ('1,00','15五','一百百','999负','1e3万万'):
            self.assertTrue(B.check_numbers('999和15',{'reply_text':token})[1],token)
