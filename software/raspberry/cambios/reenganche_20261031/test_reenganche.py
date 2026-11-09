import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"corridas/20261031_210305/programas_rpi"))
import numpy as np
from recuperacion_guard import RecoveryGuard

class SearchTests(unittest.TestCase):
 def setUp(self):
  self.empty=np.zeros((120,160),np.uint8)
  self.left=self.empty.copy();self.left[60:76,5:20]=255
  self.right=np.fliplr(self.left).copy()
  self.center=self.empty.copy();self.center[60:,75:85]=255
 def guard(self,mask):
  g=RecoveryGuard();g.evidence=dict(side=1,left=0,right=20)
  g.remember_fragment(mask,10.0);g.begin_finish(1,10.0)
  return g
 def test_same_codo_search_follows_fragment_not_branch(self):
  for mask,expected in [(self.left,85),(self.right,-85)]:
   g=self.guard(mask)
   self.assertIsNone(g.finish(10.0,self.empty,self.empty,0))
   result=g.finish(10.36,self.empty,self.empty,0)
   self.assertEqual(result,dict(action='SEARCH',angle=expected))
 def test_no_blind_retry_without_recent_visual_or_branch(self):
  for mode in ['stale','no_branch','no_fragment']:
   g=self.guard(self.left)
   if mode=='stale':g.fragment=(7.0,-.8)
   if mode=='no_branch':g.evidence['side']=0
   if mode=='no_fragment':g.fragment=None
   g.finish(10.0,self.empty,self.empty,0)
   self.assertEqual(g.finish(10.36,self.empty,self.empty,0)['action'],'STOP')
 def test_deadline_stops_and_cannot_repeat(self):
  g=self.guard(self.left);g.finish(10.0,self.empty,self.empty,0)
  g.finish(10.36,self.empty,self.empty,0)
  self.assertEqual(g.finish(11.37,self.empty,self.left,0)['action'],'STOP')
  self.assertEqual(g.finish(11.40,self.empty,self.left,0)['action'],'STOP')
 def test_rehook_requires_three_centered_oriented_frames(self):
  g=self.guard(self.left);g.finish(10.0,self.empty,self.empty,0);g.finish(10.36,self.empty,self.empty,0)
  for t in [10.4,10.44]:
   self.assertIsNone(g.finish(t,self.center,self.center,0));self.assertIsNotNone(g.search_t)
  g.finish(10.48,self.center,self.center,0)
  self.assertIsNone(g.search_t);self.assertEqual(g.finish_side,0)
 def test_reset_prevents_leaking_search_into_next_mark_or_episode(self):
  g=self.guard(self.left);g.finish(10.0,self.empty,self.empty,0);g.finish(10.36,self.empty,self.empty,0)
  g.reset();self.assertIsNone(g.finish(10.4,self.empty,self.left,0))
if __name__=='__main__':unittest.main()
