import unittest
from unittest.mock import Mock
import cv2
import numpy as np
from doble_transversal import EarlyDouble
from pathlib import Path
import importlib.util
import tempfile
import shutil
import contextlib
import io


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
        lab[42:55,20:55]=[15,128,128]
        lab[52:65,105:140]=[15,128,128]
        black=np.zeros((120,160),np.uint8)
        black[60:120,70:90]=255
        black[60:65,105:140]=255
        black[65:85,55:105]=255
        self.assertIsNotNone(self.detector.evidence(lab,black))
        black[65:85,55:105]=0
        self.assertIsNone(self.detector.evidence(lab,black))

    def test_top_greens_are_discarded_and_only_bottom_left_remains_simple(self):
        image=np.full((120,160,3),240,np.uint8)
        image[70:80]=20
        image[:,75:85]=20
        green=cv2.cvtColor(np.uint8([[[100,103,128]]]),cv2.COLOR_LAB2BGR)[0,0]
        image[48:68,30:60]=green
        image[48:68,105:135]=green
        image[82:107,30:60]=green
        lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)
        black=cv2.inRange(image,np.array([0,0,0]),np.array([90,90,90]));black[:60]=0
        for now in [.01,.05,.09]:
            self.assertIsNone(self.detector.evidence(lab,black))
            self.assertEqual(self.detector.step(1,lab,black,now),1)

    def test_user_correct_left_is_preserved_on_recorded_frames(self):
        raw=Path(__file__).resolve().parents[3]/'raspberry/corridas/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926'
        detector=EarlyDouble(Passthrough(),[60,90,110],[198,111,137])
        for index,n in enumerate([9970,9971,9972]):
            image=cv2.imread(str(raw/f'f_{n:06d}.png'))
            self.assertIsNotNone(image)
            lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)
            black=cv2.inRange(image,np.array([0,0,0]),np.array([90,90,90]));black[:60]=0
            self.assertIsNone(detector.evidence(lab,black))
            self.assertEqual(detector.step(1,lab,black,.01+index*.04),1)

    def test_real_early_double_is_confirmed_before_first_simple(self):
        raw=Path(__file__).resolve().parents[3]/'raspberry/corridas/20261101_124912/crudo_doble_dato_20261101_124912/1101_124926'
        detector=EarlyDouble(Passthrough(),[60,90,110],[198,111,137])
        for index,(n,state,expected) in enumerate([(1649,0,0),(1650,0,0),(1651,2,3)]):
            image=cv2.imread(str(raw/f'f_{n:06d}.png'));lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)
            black=cv2.inRange(image,np.array([0,0,0]),np.array([90,90,90]));black[:60]=0
            self.assertEqual(detector.step(state,lab,black,.01+index*.04),expected)

    def test_installer_preserves_main_and_backs_up_previous_helper(self):
        from desplegar import install
        here=Path(__file__).resolve().parent
        base=here.parents[2]/'raspberry/corridas/20261101_124912'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ['main.py','doble_dato.py']:shutil.copy2(base/name,root/name)
            original_main=(root/'main.py').read_bytes()
            original_helper=(root/'doble_dato.py').read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):backup=install(root)
            self.assertEqual((root/'main.py').read_bytes(),original_main)
            self.assertEqual((backup/'doble_dato.py').read_bytes(),original_helper)
            self.assertEqual((root/'doble_transversal.py').read_bytes(),(here/'doble_transversal.py').read_bytes())
            with self.assertRaises(ValueError):install(root) # no pisar una version ya distinta

    def test_calibrator_can_preview_new_helper_and_tracks_core_hash(self):
        here=Path(__file__).resolve().parent
        path=here.parent/'calibrador_verdes_express_20261102/calibrador_verdes_express.py'
        spec=importlib.util.spec_from_file_location('express_compatibility',path)
        tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
        detector=tool.Detector(here/'integracion_verificada/main.py')
        self.assertIn('doble_transversal.py',detector.hashes)
        white=np.full((120,160,3),255,np.uint8)
        self.assertEqual(detector.evaluate(white,detector.lower,detector.upper),0)
        instance=detector.double.DoubleData()
        detector.evaluate(white,[70,92,112],[190,110,135],True,instance)
        self.assertEqual(instance._early.lower.tolist(),[60,92,112])
        self.assertEqual(instance._early.upper.tolist(),[190,111,137])


if __name__=='__main__':unittest.main(verbosity=2)
