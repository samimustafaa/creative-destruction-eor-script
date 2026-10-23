import ast
import ctypes
from ctypes import wintypes
import importlib.util
import json
from pathlib import Path
import queue
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock,patch

path=Path(__file__).resolve().parents[1]/'creative_destruction_edit.py'
spec=importlib.util.spec_from_file_location('quickedit_keys',path)
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)

class EditKeyChecks(unittest.TestCase):
    def test_supported_and_reserved_keys(self):
        for text,name,vk in [('e','E',69),(' v ','V',86),('1','1',49),('tab','Tab',9),('SPACE','Space',32),('F1','F1',112),('F12','F12',123)]:
            self.assertEqual(app.parse_edit_key(text),(name,vk))
        for invalid in ['F6','F10','Esc','Escape','Ctrl+E','Mouse4','','é']:
            with self.assertRaises(ValueError):app.parse_edit_key(invalid)
    def test_persistence_and_corrupt_config_fallback(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(app.os.environ,{'LOCALAPPDATA':folder}):
            self.assertEqual(app.load_edit_key(),'G')
            app.edit_settings_path().parent.mkdir(parents=True)
            app.edit_settings_path().write_text('{"other_setting":42}')
            app.save_edit_key('E');self.assertEqual(app.load_edit_key(),'E')
            self.assertEqual(json.loads(app.edit_settings_path().read_text())['other_setting'],42)
            for value in ['bad json','{"edit_key":"F10"}','[]','null']:
                app.edit_settings_path().write_text(value);self.assertEqual(app.load_edit_key(),'G')
    def hook(self,key='E',foreground=111):
        main=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        fn=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='keyboard');fn.decorator_list=[]
        args=types.SimpleNamespace(edit_vk=app.parse_edit_key(key)[1])
        state={'enabled':True,'editing':False,'window':None}
        def reset():state.update(editing=False,window=None)
        user=types.SimpleNamespace(CallNextHookEx=lambda *a:0,GetCursorPos=lambda *a:False,GetAsyncKeyState=lambda *a:0)
        env=dict(C=types.SimpleNamespace(cast=lambda data,kind:types.SimpleNamespace(contents=data),POINTER=lambda kind:kind,byref=ctypes.byref),KeyboardHook=object,W=wintypes,user=user,args=args,state=state,state_lock=threading.RLock(),keys_down=set(),reset=reset,foreground_game=lambda:foreground,wake=threading.Event(),notify_hooks=Mock(),report=Mock(),ui_events=queue.Queue())
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'keyboard-test','exec'),env)
        def send(vk,up=False,flags=0):env['keyboard'](0,0x101 if up else 0x100,types.SimpleNamespace(vkCode=vk,flags=flags))
        return env,send
    def test_custom_bind_overrides_cancel_and_build_keys(self):
        for key in ['E','F','X','C','1','Tab','Space','V','G']:
            env,send=self.hook(key);vk=env['args'].edit_vk
            send(vk);self.assertTrue(env['state']['editing'],key)
            send(vk);self.assertTrue(env['state']['editing'],'Repeat toggled edit')
            send(vk,up=True);send(vk);self.assertFalse(env['state']['editing'],key)
    def test_old_key_ignored_and_old_release_cleans_key_state(self):
        env,send=self.hook('G');send(71);env['args'].edit_vk=69
        send(71,up=True);self.assertNotIn(71,env['keys_down'])
        env['reset']();send(71);self.assertFalse(env['state']['editing'])
        env['args'].edit_vk=71;send(71);self.assertTrue(env['state']['editing'])
    def test_foreground_injection_and_app_hotkeys(self):
        env,send=self.hook('E',foreground=None);send(69);self.assertFalse(env['state']['editing'])
        env,send=self.hook('E');send(69,flags=0x10);self.assertFalse(env['state']['editing'])
        send(69);send(27);self.assertFalse(env['state']['editing'])
        send(117);self.assertFalse(env['state']['enabled'])
        send(121);self.assertEqual(env['ui_events'].get_nowait(),('quit',None))
    def make_ui(self,key):
        ui=app.AppUI.__new__(app.AppUI);ui.values=[Mock(get=lambda v=v:v) for v in (10,8,8,144)]
        ui.edit_key=Mock(get=lambda:key);ui.process=Mock(get=lambda:'client.exe')
        ui.select_only=Mock(get=lambda:False);ui.auto_reset=Mock(get=lambda:True)
        ui.args=types.SimpleNamespace(edit_key='G',edit_vk=71);ui.state={'enabled':True}
        for name in ['reset','paint_presets','show_success','refresh','root','messagebox']:setattr(ui,name,Mock())
        return ui
    def test_apply_updates_runtime_and_saves_key(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(app.os.environ,{'LOCALAPPDATA':folder}):
            ui=self.make_ui('e');self.assertTrue(ui.apply())
            self.assertEqual((ui.args.edit_key,ui.args.edit_vk),('E',69))
            self.assertEqual(app.load_edit_key(),'E');self.assertFalse(ui.state['enabled'])
    def test_invalid_bind_or_save_failure_preserves_runtime(self):
        for key in ['F10','Ctrl+E']:
            ui=self.make_ui(key);self.assertFalse(ui.apply());self.assertTrue(ui.state['enabled']);self.assertEqual(ui.args.edit_vk,71)
        ui=self.make_ui('E')
        with patch.object(app,'save_edit_key',side_effect=OSError('read only')):
            self.assertFalse(ui.apply());self.assertTrue(ui.state['enabled']);self.assertEqual(ui.args.edit_vk,71)

if __name__=='__main__':unittest.main()
