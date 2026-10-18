"""System-tray lifecycle checks without creating a native tray icon."""
import importlib.util
from pathlib import Path
import queue
import sys
import threading
import types
import unittest
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location('quickedit',Path(__file__).resolve().parents[1]/'creative_destruction_edit.py')
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)

class TrayChecks(unittest.TestCase):
    def make_ui(self):
        ui=app.AppUI.__new__(app.AppUI)
        ui.root=Mock();ui.root.state.return_value='withdrawn'
        ui.state={'enabled':True,'editing':False,'stage':'select'}
        ui.stop=threading.Event();ui.reset=Mock();ui.last=Mock();ui.events=queue.Queue()
        ui.tray=None;ui.tray_ready=False;ui.tray_starting=False;ui.tray_enabled=None;ui.closing=False
        ui.app_art=Mock();ui.canvas=Mock();ui.foreground_game=Mock(side_effect=AssertionError('Hidden UI queried foreground process'))
        return ui
    def test_close_hides_without_stopping_helper(self):
        ui=self.make_ui();ui.tray_ready=True;ui.hide_to_tray()
        ui.root.withdraw.assert_called_once();ui.root.destroy.assert_not_called()
        self.assertTrue(ui.state['enabled']);self.assertFalse(ui.stop.is_set());ui.reset.assert_not_called()
    def test_show_reopens_window(self):
        ui=self.make_ui();ui.show_window()
        ui.root.deiconify.assert_called_once();ui.root.lift.assert_called_once();ui.root.focus_force.assert_called_once()
    def test_quit_removes_icon_and_stops_once(self):
        ui=self.make_ui();ui.tray=Mock();ui.close();ui.close()
        self.assertFalse(ui.state['enabled']);self.assertTrue(ui.stop.is_set())
        ui.tray.stop.assert_called_once();ui.root.destroy.assert_called_once();ui.reset.assert_called_once()
    def test_missing_tray_does_not_strand_app(self):
        ui=self.make_ui();ui.hide_to_tray();self.assertTrue(ui.stop.is_set())
        ui=self.make_ui();ui.tray_starting=True;ui.hide_to_tray()
        self.assertFalse(ui.stop.is_set());ui.root.withdraw.assert_not_called();ui.last.set.assert_called_once()
    def test_hidden_refresh_skips_paint_and_process_lookup(self):
        ui=self.make_ui();ui.refresh(schedule=False)
        ui.foreground_game.assert_not_called();ui.canvas.itemconfigure.assert_not_called()
    def test_tray_failure_restores_accessible_window(self):
        ui=self.make_ui();ui.tray_ready=True;ui.show_window=Mock()
        ui.events.put(('tray_error','failed'));ui.refresh(schedule=False)
        self.assertFalse(ui.tray_ready);ui.show_window.assert_called_once()
    def test_native_menu_callbacks_only_queue_ui_events(self):
        ui=self.make_ui()
        class Menu:
            SEPARATOR=object()
            def __init__(self,*items):self.items=items
        class Item:
            def __init__(self,text,action,**kw):self.text=text;self.action=action
        def icon(name,image,title,menu):return types.SimpleNamespace(menu=menu)
        fake=types.SimpleNamespace(Menu=Menu,MenuItem=Item,Icon=icon)
        with patch.object(app,'os',types.SimpleNamespace(name='nt')),patch.dict(sys.modules,{'pystray':fake}),patch.object(app.threading,'Thread') as thread:
            ui.start_tray();thread.return_value.start.assert_called_once()
        self.assertTrue(ui.tray_starting)
        for index,event in [(0,'show'),(1,'toggle'),(3,'quit')]:
            ui.tray.menu.items[index].action(None,None);self.assertEqual(ui.events.get_nowait(),(event,None))
        ui.root.deiconify.assert_not_called();ui.root.destroy.assert_not_called()
        toggle=ui.tray.menu.items[1];self.assertEqual(toggle.text(None),'Pause helper')
        ui.state['enabled']=False;self.assertEqual(toggle.text(None),'Start helper')

if __name__=='__main__':unittest.main()
