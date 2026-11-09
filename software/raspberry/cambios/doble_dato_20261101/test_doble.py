import unittest
import numpy as np
from doble_dato import DoubleData


class Tests(unittest.TestCase):
    def scene(self, double=True):
        lab = np.full((120, 160, 3), [240, 128, 128], dtype=np.uint8)
        black = np.zeros((120, 160), np.uint8)
        black[90:, 75:85] = 255
        lab[70:115, 110:150] = [70, 105, 128]
        black[60:70, 110:150] = 255
        if double:
            lab[70:79, 30:65] = [70, 105, 128]
            black[60:70, 30:65] = 255
        return lab, black

    def test_double_before_second_patch_reaches_row80(self):
        lab, black = self.scene()
        self.assertEqual(DoubleData().step(2, lab, black, 10), 3)

    def test_single_unchanged(self):
        lab, black = self.scene(False)
        self.assertEqual(DoubleData().step(2, lab, black, 10), 2)

    def test_background_or_rejected_marker_does_not_start_event(self):
        lab, black = self.scene()
        self.assertEqual(DoubleData().step(0, lab, black, 10), 0)

    def test_double_identity_survives_occlusion_and_brief_gap(self):
        lab, black = self.scene()
        g = DoubleData()
        self.assertEqual(g.step(2, lab, black, 10), 3)
        lab, black = self.scene(False)
        self.assertEqual(g.step(1, lab, black, 10.04), 3)
        self.assertEqual(g.step(0, None, None, 10.12), 3)
        self.assertEqual(g.step(0, None, None, 10.25), 0)
        self.assertEqual(g.step(2, lab, black, 10.30), 2)

    def test_priority_states_and_pause_clear_memory(self):
        lab, black = self.scene()
        for state in (4, 18, 19):
            g = DoubleData()
            g.step(2, lab, black, 10)
            self.assertEqual(g.step(state, None, None, 10.04), state)
            self.assertEqual(g.step(2, *self.scene(False), 10.08), 2)
        g = DoubleData()
        g.step(2, lab, black, 10)
        self.assertEqual(g.step(2, *self.scene(False), 11), 2)

    def test_pair_requires_black_above_both_patches(self):
        lab, black = self.scene()
        black[60:70, 30:65] = 0
        self.assertEqual(DoubleData().step(2, lab, black, 10), 2)


if __name__ == '__main__':
    unittest.main()
