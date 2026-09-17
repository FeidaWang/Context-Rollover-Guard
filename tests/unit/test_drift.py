import math
import unittest
from crg.calibration_online import drift,score,update_bias,metrics


class DriftTests(unittest.TestCase):
    def test_shift_sparse_and_recovery(self):
        p={'interval':[90,110],'median':100}
        self.assertFalse(drift([score(p,100)]*3)['fallback'])
        self.assertTrue(drift([score(p,v) for v in range(120,160,2)])['fallback'])
        self.assertTrue(drift([score(p,1000)]*20)['fallback'])
        self.assertFalse(drift([score(p,1000)]*20+[score(p,100)]*20)['fallback'])
        self.assertEqual(metrics([score(p,100)])['interval_width'],20)

    def test_bias_equation(self):
        bias,base,actual=.5,math.log1p(10),20
        expected=bias+.1*(math.log1p(actual)-(base+bias))
        self.assertAlmostEqual(update_bias(bias,base,actual),expected)
