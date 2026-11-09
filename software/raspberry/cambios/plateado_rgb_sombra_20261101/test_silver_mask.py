"""Comprueba que una hipotesis no se transforme en una orden ni sobreviva sin imagen."""
from pathlib import Path
import unittest
import cv2
import numpy as np
from silver_mask import SilverShadow, detect_band

BASE = Path(__file__).resolve().parent
RAW = BASE.parents[1] / 'corridas/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926'


class ShadowTests(unittest.TestCase):
    def test_reflejo_aislado_no_forma_banda(self):
        image = np.full((120, 160, 3), 235, np.uint8)
        cv2.circle(image, (80, 85), 12, (160, 160, 160), -1)
        self.assertIsNone(detect_band(image)[2])

    def test_codo_negro_solo_no_es_material(self):
        image = np.full((120, 160, 3), 235, np.uint8)
        cv2.line(image, (80, 119), (80, 75), (15, 15, 15), 14)
        cv2.line(image, (80, 75), (5, 75), (15, 15, 15), 14)
        self.assertIsNone(detect_band(image)[2])

    def test_desaparicion_no_conserva_pose(self):
        image = cv2.imread(str(RAW / 'f_015320.png'))
        self.assertIsNotNone(image)
        guard = SilverShadow()
        for t in [1., 1.04, 1.08]:
            result = guard.step(image, t)
        self.assertTrue(result['stable'])
        self.assertIsNone(result['motor_command'])
        self.assertIsNone(result['centered'])
        missing = guard.step(np.full_like(image, 235), 1.12)
        self.assertIsNone(missing['slope'])
        self.assertFalse(missing['stable'])

    def test_pausa_exige_confirmar_nuevamente(self):
        image = cv2.imread(str(RAW / 'f_015320.png'))
        guard = SilverShadow()
        for t in [1., 1.04, 1.08]:
            guard.step(image, t)
        result = guard.step(image, 2.)
        self.assertFalse(result['stable'])
        self.assertEqual(result['frames'], 1)


if __name__ == '__main__':
    unittest.main()
