import unittest,ast
from pathlib import Path
import numpy as np
from verde_oscuro import detectar_verde_sombra
class Tests(unittest.TestCase):
 def scene(self,rectangles):
  lab=np.empty((120,160,3),np.uint8);lab[:]=[240,128,128];black=np.zeros((120,160),np.uint8);black[90:,75:85]=255
  for a,b in rectangles:lab[80:120,a:b]=[70,105,128];black[60:90,a:b]=255
  return lab,black
 def detect(self,rects):
  lab,black=self.scene(rects);return detectar_verde_sombra(lab,black,np.array([120,90,110]),np.array([198,109,134]),200,1.)[0]
 def test_sides_and_true_double(self):
  self.assertEqual(self.detect([(10,50)]),1);self.assertEqual(self.detect([(110,150)]),2);self.assertEqual(self.detect([(10,50),(110,150)]),3)
 def test_fragments_same_side_are_not_double(self):self.assertEqual(self.detect([(90,111),(120,145)]),2)
 def test_cross_gate_and_reference_required(self):
  lab,black=self.scene([(10,50)]);black[:90]=0
  self.assertEqual(detectar_verde_sombra(lab,black,np.array([120,90,110]),np.array([198,109,134]),200,1.)[0],0)
  black[:]=0;self.assertEqual(detectar_verde_sombra(lab,black,np.array([120,90,110]),np.array([198,109,134]),200,1.)[0],0)
 def test_small_patch_rejected(self):self.assertEqual(self.detect([(10,20)]),0)
 def test_existing_dark_function_identical(self):
  b=Path(__file__).resolve().parent;old=ast.parse((b.parents[1]/'corridas/20261101_111110/verde_oscuro.py').read_text());new=ast.parse((b/'verde_oscuro.py').read_text())
  f=lambda t:next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='detectar_verde_oscuro')
  self.assertEqual(ast.dump(f(old)),ast.dump(f(new)))
if __name__=='__main__':unittest.main()
