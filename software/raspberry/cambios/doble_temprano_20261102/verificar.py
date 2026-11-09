import unittest
from unittest.mock import Mock
import cv2
import numpy as np
from doble_temprano import EarlyDouble


class Passthrough:
    def step(self,state,lab,black,now):return state


class Checks(unittest.TestCase):
    def setUp(self):
        self.detector=EarlyDouble(Passthrough(),[54,95,120],[132,112,139])
        self.lab=np.zeros((120,160,3),np.uint8)
        self.black=np.zeros((120,160),np.uint8)
        self.pair=dict(centers=[[40,70],[120,75]])

    def test_never_creates_new_marker_from_zero(self):
        self.detector.evidence=Mock(return_value=self.pair)
        for t in [.01,.05,.09]:self.assertEqual(self.detector.step(0,self.lab,self.black,t),0)

    def test_two_observations_before_acceptance_promote_first_simple(self):
        self.detector.evidence=Mock(return_value=self.pair)
        self.assertEqual(self.detector.step(0,self.lab,self.black,.01),0)
        self.assertEqual(self.detector.step(2,self.lab,self.black,.05),3)

    def test_no_pair_preserves_all_simple_decisions(self):
        self.detector.evidence=Mock(return_value=None)
        for i,state in enumerate([0,1,2,1,0,2]):
            self.assertEqual(self.detector.step(state,self.lab,self.black,.01+i*.04),state)

    def test_one_frame_hint_does_not_turn_simple_into_double(self):
        self.detector.evidence=Mock(side_effect=[self.pair,None])
        self.assertEqual(self.detector.step(2,self.lab,self.black,.01),0)
        self.assertEqual(self.detector.step(2,self.lab,self.black,.05),2)

    def test_old_double_is_never_shortened_by_early_clock(self):
        self.detector.evidence=Mock(return_value=self.pair)
        self.detector.step(0,self.lab,self.black,.01)
        self.detector.step(2,self.lab,self.black,.05)
        for t in [.1,.2,.35,.5,.65,.8,.95,1.1]:
            self.assertEqual(self.detector.step(3,self.lab,self.black,t),3)

    def test_gap_resets_pair_confirmation(self):
        self.detector.evidence=Mock(return_value=self.pair)
        self.detector.step(0,self.lab,self.black,.01)
        self.assertEqual(self.detector.step(2,self.lab,self.black,.5),0)

    def test_black_separator_required_on_real_masks(self):
        # Dos verdes bien separados, con linea negra entre ellos.
        lab=np.full((120,160,3),[230,128,128],np.uint8)
        lab[55:85,20:55]=[100,103,128]
        lab[65:95,105:140]=[100,103,128]
        black=np.zeros((120,160),np.uint8)
        black[60:120,70:90]=255
        black[60:65,105:140]=255
        black[65:85,55:105]=255
        self.assertIsNotNone(self.detector.evidence(lab,black))
        black[65:85,55:105]=0
        self.assertIsNone(self.detector.evidence(lab,black))


if __name__=='__main__':unittest.main(verbosity=2)
