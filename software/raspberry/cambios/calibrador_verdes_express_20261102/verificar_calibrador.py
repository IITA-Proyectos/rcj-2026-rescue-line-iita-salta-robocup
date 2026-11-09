"""Prueba funcional offline. No requiere camara, serial ni modificar el robot."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import itertools
import zipfile
from unittest.mock import patch, MagicMock

import cv2
import numpy as np

import calibrador_verdes_express as tool

SOFTWARE = Path(__file__).resolve().parents[3]
BASE = SOFTWARE/'raspberry/corridas/20261101_124912'


def scene(state, light=150):
    image=np.full((120,160,3),240,np.uint8)
    image[60:120,76:85]=20
    image[65:80,:]=20
    color=cv2.cvtColor(np.uint8([[[light,100,125]]]),cv2.COLOR_LAB2BGR)[0,0]
    if state in (1,3):image[90:116,20:50]=color
    if state in (2,3):image[90:116,110:140]=color
    return image


class Checks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        for name in tool.NAMES:shutil.copy2(BASE/name,self.root/name)
        self.detector=tool.Detector(self.root/'main.py')

    def tearDown(self):self.temp.cleanup()

    def samples(self):
        items=[]
        for i,light in enumerate([130,150,170]):
            path=self.root/('green%d.png'%i)
            cv2.imwrite(str(path),scene(1,light))
            items.append(dict(image=str(path),kind='green',roi=[23,93,20,18]))
        for i,color in enumerate([240,20,140]):
            path=self.root/('negative%d.png'%i)
            cv2.imwrite(str(path),np.full((120,160,3),color,np.uint8))
            items.append(dict(image=str(path),kind='negative',roi=[20,90,20,20]))
        for state in range(4):
            path=self.root/('scene%d.png'%state)
            image=scene(state)
            if state==1:
                image[90:116,20:50]=240
                color=cv2.cvtColor(np.uint8([[[150,100,125]]]),cv2.COLOR_LAB2BGR)[0,0]
                image[90:116,22:52]=color
            cv2.imwrite(str(path),image)
            items.append(dict(image=str(path),kind='scene',expected=state))
        return items

    def test_simple_double_and_discard(self):
        for state in range(4):
            for light in [130,150,170]:
                self.assertEqual(self.detector.evaluate(scene(state,light),self.detector.lower,self.detector.upper),state)

    def test_dark_and_shadow_backups(self):
        for light in [80,110]:
            for state in [1,2,3]:
                self.assertEqual(self.detector.evaluate(scene(state,light),self.detector.lower,self.detector.upper),state)

    def test_fit_check_apply_and_backup(self):
        items=self.samples()
        lower,upper=tool.fit(items)
        report=tool.validate(self.detector,items,lower,upper)
        self.assertTrue(report['passed'],report['errors'])
        profile=dict(version=tool.VERSION,hashes=self.detector.hashes,lower=lower,upper=upper,
                     samples=items,camera_environment={k:tool.os.getenv(k,'') for k in ['CAMARA_WB','CAMARA_EXPO','DOBLE_SIN_FACTOR']})
        path=self.root/'profile.json';path.write_text(json.dumps(profile))
        before={name:(self.root/name).read_bytes() for name in tool.NAMES}
        with contextlib.redirect_stdout(io.StringIO()):tool.apply_profile(self.detector,path)
        updated=tool.Detector(self.root/'main.py')
        self.assertEqual(updated.lower,lower)
        self.assertEqual(updated.minimum,self.detector.minimum)
        self.assertEqual((self.root/'verde_oscuro.py').read_bytes(),before['verde_oscuro.py'])
        backups=list(self.root.glob('respaldo_verdes_*'))
        self.assertEqual(len(backups),1)
        for name,content in before.items():self.assertEqual((backups[0]/name).read_bytes(),content)
        for state in range(4):self.assertEqual(updated.evaluate(scene(state),lower,upper,False),state)
        with self.assertRaises(ValueError):tool.apply_profile(updated,path)

    def test_negatives_block_even_when_only_shadow_accepts(self):
        items=self.samples()
        lo,hi=tool.fit(items)
        color=cv2.cvtColor(np.uint8([[[80,100,125]]]),cv2.COLOR_LAB2BGR)[0,0]
        path=self.root/'ambiguous.png'
        cv2.imwrite(str(path),np.full((120,160,3),color,np.uint8))
        items.append(dict(image=str(path),kind='negative',roi=[10,90,20,20]))
        result=tool.validate(self.detector,items,lo,hi)
        self.assertFalse(result['passed'])
        self.assertTrue(any('Negativo confundido' in error for error in result['errors']))

    def test_wrong_expected_side_blocks_profile(self):
        items=self.samples();lo,hi=tool.fit(items)
        items[-1]['expected']=1
        result=tool.validate(self.detector,items,lo,hi)
        self.assertFalse(result['passed'])
        self.assertTrue(any('esperaba 1, da 3' in error for error in result['errors']))

    def test_rectangle_updates_while_dragging_and_clips_to_image(self):
        ui=tool.ExpressUI()
        ui.mouse(cv2.EVENT_LBUTTONDOWN,200,200)
        self.assertTrue(ui.freeze_requested)
        ui.mouse(cv2.EVENT_MOUSEMOVE,280,300)
        self.assertEqual(ui.roi,[50,50,21,26])
        self.assertIsNotNone(ui.start)
        ui.mouse(cv2.EVENT_LBUTTONUP,900,600)
        self.assertEqual(ui.roi,[50,50,110,70])
        self.assertIsNone(ui.start)

    def test_buttons_dispatch_without_selecting_image(self):
        ui=tool.ExpressUI()
        ui.mouse(cv2.EVENT_LBUTTONDOWN,230,500)
        self.assertEqual(ui.actions,[])  # navegacion desactivada en camara
        ui.can_navigate=True
        ui.mouse(cv2.EVENT_LBUTTONDOWN,230,500)
        self.assertEqual(ui.actions,['d'])
        self.assertIsNone(ui.roi)
        ui.mouse(cv2.EVENT_LBUTTONDOWN,660,500)
        self.assertEqual(ui.actions,['d','g'])

    def test_saved_rectangle_is_visible_only_on_its_frame(self):
        ui=tool.ExpressUI()
        im=scene(1)
        item=dict(kind='green',roi=[22,92,20,18],frame_key=tool.frame_key(im))
        masks=self.detector.masks(im,self.detector.lower,self.detector.upper)
        panel=tool.render_panel(im,masks,ui,[item],'OK',[])
        self.assertEqual(panel.shape,(710,1280,3))
        self.assertTrue(np.array_equal(panel[92*4,22*4],(70,230,70)))
        item['frame_key']='otra imagen'
        other=tool.render_panel(im,masks,ui,[item],'OK',[])
        self.assertFalse(np.array_equal(other[92*4,22*4],(70,230,70)))

    def test_live_camera_freezes_selection_and_saves_unmodified_frame(self):
        camera=MagicMock()
        camera.isOpened.return_value=True
        camera.read.return_value=(True,cv2.rotate(scene(1),cv2.ROTATE_180))
        callback=[]
        panels=[]
        def show(name,panel):
            panels.append(panel)
            if len(panels)==1:
                callback[0](cv2.EVENT_LBUTTONDOWN,92,372,0,None)
                callback[0](cv2.EVENT_MOUSEMOVE,164,436,0,None)
                callback[0](cv2.EVENT_LBUTTONUP,164,436,0,None)
        argv=['calibrador','--main',str(self.root/'main.py'),'--out',str(self.root/'live'),'--selection','rectangle']
        with patch('sys.argv',argv), patch.object(cv2,'VideoCapture',return_value=camera), \
             patch.object(cv2,'namedWindow'), patch.object(cv2,'setMouseCallback',side_effect=lambda name,fn:callback.append(fn)), \
             patch.object(cv2,'imshow',side_effect=show), patch.object(cv2,'waitKey',side_effect=[ord('g'),ord('p'),ord('q')]), \
             patch.object(cv2,'destroyAllWindows'), patch.object(tool,'camera_controls'), \
             contextlib.redirect_stdout(io.StringIO()):
            tool.main()
        items=json.loads((self.root/'live/muestras.json').read_text())
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['kind'],'green')
        self.assertTrue(np.array_equal(cv2.imread(items[0]['image']),scene(1)))
        self.assertEqual(camera.read.call_count,14) # 12 estabilizacion, 1 inicial, 1 al volver a vivo
        camera.release.assert_called_once()

    def test_clean_video_seeking_and_orientation(self):
        path=self.root/'clean.avi'
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),20.,(160,120))
        self.assertTrue(writer.isOpened())
        for state in [1,2,3,0]:writer.write(scene(state))
        writer.release()
        video=tool.VideoFrames(path)
        try:
            self.assertEqual(video.total,4)
            self.assertEqual(self.detector.evaluate(video.read(2),self.detector.lower,self.detector.upper),3)
            self.assertEqual(self.detector.evaluate(video.read(0),self.detector.lower,self.detector.upper),1)
            video.read(200);self.assertEqual(video.index,3)
            video.read(-10);self.assertEqual(video.index,0)
        finally:video.release()

    def test_video_mask_panel_is_rejected(self):
        path=self.root/'overlay.avi'
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),20.,(640,240))
        self.assertTrue(writer.isOpened())
        writer.write(np.zeros((240,640,3),np.uint8));writer.release()
        with self.assertRaisesRegex(ValueError,'panel de mascaras'):tool.VideoFrames(path)

    def test_four_corners_work_in_every_click_order(self):
        corners=[[20,40],[80,45],[70,80],[25,85]]
        for order in itertools.permutations(corners):
            polygon=tool.quadrilateral(order)
            self.assertEqual(len(polygon),4)
            self.assertTrue(cv2.isContourConvex(np.array(polygon,np.int32)))

    def test_bad_fourth_point_is_not_silently_saved_as_triangle(self):
        ui=tool.ExpressUI();ui.mode='points'
        for x,y in [(20,20),(80,20),(80,80)]:ui.add_point(x,y)
        ui.add_point(65,40) # dentro del triangulo
        self.assertEqual(len(ui.points),3)
        self.assertIsNone(ui.polygon)
        self.assertIsNone(ui.roi)
        ui.add_point(20,80)
        self.assertEqual(len(ui.points),4)
        self.assertIsNotNone(ui.polygon)
        ui.remove_point()
        self.assertEqual(len(ui.points),3)
        self.assertIsNone(ui.polygon)

    def test_polygon_samples_only_inside_not_bounding_rectangle(self):
        image=np.full((120,160,3),255,np.uint8)
        poly=[[60,40],[90,70],[60,100],[30,70]]
        color=cv2.cvtColor(np.uint8([[[150,100,125]]]),cv2.COLOR_LAB2BGR)[0,0]
        cv2.fillConvexPoly(image,np.array(poly,np.int32),color.tolist())
        pixels=tool.sample_pixels(image,dict(roi=[30,40,61,61],polygon=poly))
        expected=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)[70,60]
        self.assertTrue(np.all(pixels==expected))
        rectangle=tool.sample_pixels(image,dict(roi=[30,40,61,61]))
        self.assertTrue(np.any(rectangle[:,1]>120))

    def test_points_mode_clicks_freeze_camera_and_right_click_removes(self):
        ui=tool.ExpressUI();ui.mode='points'
        for x,y in [(200,200),(300,200),(300,300),(200,300)]:
            ui.mouse(cv2.EVENT_LBUTTONDOWN,x,y)
            ui.mouse(cv2.EVENT_LBUTTONUP,x,y)
        self.assertTrue(ui.freeze_requested)
        self.assertIsNotNone(ui.polygon)
        ui.mouse(cv2.EVENT_RBUTTONDOWN,200,300)
        self.assertEqual(len(ui.points),3)
        self.assertIsNone(ui.polygon)

    def test_delete_picks_outline_of_older_rectangle_without_touching_later_tests(self):
        samples=[dict(kind='green',frame_key='same',roi=[0,50,35,40]),
                 dict(kind='green',frame_key='same',roi=[2,53,40,34],polygon=[[2,53],[41,56],[32,86],[2,78]]),
                 dict(kind='scene',frame_key='same',expected=1)]
        index=tool.pick_saved_sample(samples,'same',(0,70))
        self.assertEqual(index,0)
        samples.pop(index)
        self.assertEqual(samples[-1]['kind'],'scene')
        self.assertIsNone(tool.pick_saved_sample(samples,'other',(2,70)))
        self.assertIsNone(tool.pick_saved_sample(samples,'same',(120,100)))

    def test_delete_mode_does_not_start_new_selection(self):
        ui=tool.ExpressUI();ui.mode='points';ui.delete_mode=True
        ui.mouse(cv2.EVENT_LBUTTONDOWN,40,280)
        self.assertEqual(ui.delete_click,(10,70))
        self.assertEqual(ui.points,[])
        self.assertIsNone(ui.roi)

    def test_conservative_fit_preserves_old_colors_and_uses_negatives(self):
        items=self.samples()
        gray=cv2.cvtColor(np.uint8([[[100,122,128]]]),cv2.COLOR_LAB2BGR)[0,0]
        for item in items[:3]:
            image=cv2.imread(item['image']);image[93:97,23:27]=gray
            cv2.imwrite(item['image'],image)
        negative=self.root/'gray.png';cv2.imwrite(str(negative),np.full((120,160,3),gray,np.uint8))
        items.append(dict(image=str(negative),kind='negative',roi=[20,90,20,20]))
        naive_low,naive_high=tool.fit(items)
        self.assertGreater(naive_high[1],121)
        lower,upper=tool.fit_for_detector(items,self.detector)
        self.assertTrue(np.all(np.array(lower)<=self.detector.lower))
        self.assertTrue(np.all(np.array(upper)>=self.detector.upper))
        self.assertTrue(tool.validate(self.detector,items,lower,upper)['passed'])

    def test_failed_decision_saves_color_draft_but_cannot_install(self):
        items=self.samples();items[-1]['expected']=1
        lower,upper,report=tool.save_calibration(self.detector,items,self.root)
        self.assertTrue(report['color_passed'])
        self.assertFalse(report['decisions_passed'])
        self.assertTrue((self.root/'borrador_verdes.json').exists())
        self.assertFalse((self.root/'perfil_verdes.json').exists())
        with self.assertRaisesRegex(ValueError,'borrador'):
            tool.apply_profile(self.detector,self.root/'borrador_verdes.json')

    def test_reused_fit_frame_is_not_counted_as_new_validation(self):
        items=self.samples()
        left=next(s for s in items if s.get('expected')==1)
        left['image']=items[1]['image']
        low,high=tool.fit(items)
        report=tool.validate(self.detector,items,low,high)
        self.assertTrue(report['color_passed'])
        self.assertFalse(report['passed'])
        self.assertNotIn(1,report['independent_states'])

    def test_portable_export_includes_real_context_and_relative_paths(self):
        items=self.samples()
        right=next(s for s in items if s.get('expected')==2)
        source=self.root/'raw';source.mkdir()
        for n in [23,24,25]:cv2.imwrite(str(source/f'f_{n:06d}.png'),scene(2))
        right['source']=dict(image=str(source/'f_000025.png'))
        archive=tool.export_samples(items,self.root)
        target=self.root/'imported';target.mkdir()
        with zipfile.ZipFile(archive) as zipped:
            manifest=json.loads(zipped.read('muestras.json'))
            self.assertFalse(Path(manifest[0]['image']).is_absolute())
            zipped.extractall(target)
        loaded=tool.load_samples(target/'muestras.json')
        imported=next(s for s in loaded if s.get('expected')==2)
        self.assertEqual(len(imported['context']),3)
        self.assertTrue(Path(imported['context'][0]['image']).exists())
        self.assertEqual(len(tool.scene_frames(imported)),3)

    def test_scene_replays_real_timestamps_instead_of_repeating_same_frame(self):
        class Temporal:
            def __init__(self):self.times=[]
            def evaluate(self,image,lower,upper,proposed=True,double_instance=None,timestamp=None):
                self.times.append(timestamp)
                return 3 if len(self.times)>=2 else 2
        detector=Temporal()
        detector.double=type('Module',(),{'DoubleData':lambda:object()})
        frames=[(scene(3),.01),(scene(3),.06),(scene(3),.11)]
        self.assertEqual(tool.classify_scene(detector,scene(3),frames,[0]*3,[255]*3,True),3)
        self.assertEqual(detector.times,[.01,.06,.11])

    def test_protected_decision_blocks_install_without_deleting_user_labels(self):
        samples=self.samples()
        saved=json.dumps(samples,sort_keys=True)
        protection=dict(image=samples[-1]['image'],kind='scene',expected=1,protected=True)
        _,_,report=tool.save_calibration(self.detector,samples,self.root,True,[protection])
        self.assertFalse(report['passed'])
        self.assertTrue(any('PROTECCION' in s for s in report['errors']))
        self.assertEqual(json.dumps(samples,sort_keys=True),saved)
        self.assertFalse((self.root/'perfil_verdes.json').exists())

    def test_check_failure_retires_previous_profile_even_without_pressing_save(self):
        samples=self.samples();samples[-1]['expected']=1
        (self.root/'perfil_verdes.json').write_text('{}')
        _,_,report=tool.save_calibration(self.detector,samples,self.root,False)
        self.assertFalse(report['passed'])
        self.assertFalse((self.root/'perfil_verdes.json').exists())
        self.assertEqual(len(list(self.root.glob('perfil_anterior_*.json'))),1)

    def test_dark_samples_adjust_backup_without_widening_main(self):
        samples=self.samples()
        for item in samples[:3]:
            image=scene(1,50)
            cv2.imwrite(item['image'],image)
        lower,upper=tool.fit_for_detector(samples,self.detector)
        self.assertEqual(lower,self.detector.lower)
        self.assertEqual(upper,self.detector.upper)
        self.assertLess(self.detector.shadow_floor,self.detector.base_shadow_floor)
        image=scene(1,50)
        self.assertEqual(self.detector.evaluate(image,lower,upper,False),0)
        self.assertEqual(self.detector.evaluate(image,lower,upper,True),1)

    def test_install_can_change_only_backup_light_limit_with_main_unchanged(self):
        samples=self.samples()
        for item in samples[:3]:cv2.imwrite(item['image'],scene(1,50))
        before=(self.root/'main.py').read_bytes()
        _,_,report=tool.save_calibration(self.detector,samples,self.root)
        self.assertTrue(report['passed'],report['errors'])
        with contextlib.redirect_stdout(io.StringIO()):
            tool.apply_profile(self.detector,self.root/'perfil_verdes.json')
        self.assertEqual((self.root/'main.py').read_bytes(),before)
        updated=tool.Detector(self.root/'main.py')
        self.assertLess(updated.base_shadow_floor,60)
        self.assertEqual(updated.evaluate(scene(1,50),updated.lower,updated.upper,False),1)

    def test_identical_labels_are_not_counted_again_but_conflicting_labels_remain(self):
        samples=self.samples()
        image=samples[-1]['image']
        copy=dict(samples[-1]);copy['image']=image
        conflict=dict(samples[-1]);conflict['expected']=1
        cleaned=tool.remove_identical_duplicates(samples+[copy,conflict])
        self.assertEqual(len(cleaned),len(samples)+1)
        self.assertEqual({s['expected'] for s in cleaned if s.get('image')==image},{1,3})

    def test_entry_validation_checks_first_marker_not_final_double(self):
        class Temporal:
            def __init__(self):self.states=iter([0,2,3])
            def evaluate(self,*args,**kwargs):return next(self.states)
        detector=Temporal();detector.double=type('Module',(),{'DoubleData':lambda:object()})
        frames=[(scene(3),.01),(scene(3),.06),(scene(3),.11)]
        self.assertEqual(tool.classify_scene(detector,scene(3),frames,[0]*3,[255]*3,True,'entry'),2)

    def test_real_entry_was_simple_first_and_reforcement_makes_first_marker_double(self):
        raw=BASE/'crudo_doble_dato_20261101_124912/1101_124926'
        sample=dict(image=str(raw/'f_001650.png'),kind='scene',expected=3,assessment='entry',
                    source=dict(image=str(raw/'f_001650.png')))
        image=cv2.imread(sample['image'])
        frames=tool.scene_frames(sample)+tool.scene_future(sample)
        self.assertGreater(len(frames),3)
        self.assertEqual(tool.classify_scene(self.detector,image,frames,self.detector.lower,self.detector.upper,False,'entry'),2)
        combined=tool.Detector(Path(__file__).resolve().parent/'base_visual_claude_y_verdes/main.py')
        self.assertEqual(tool.classify_scene(combined,image,frames,combined.lower,combined.upper,True,'entry'),3)


if __name__=='__main__':unittest.main(verbosity=2)
