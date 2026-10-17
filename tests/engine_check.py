import ast,ctypes as C,threading,types
from ctypes import wintypes as W
from pathlib import Path
source=ast.parse((Path(__file__).resolve().parents[1]/'creative_destruction_edit.py').read_text(encoding='utf-8'));main=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main')
def function(name,env):
 node=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name==name);node.decorator_list=[]
 exec(compile(ast.Module(body=[node],type_ignores=[]),'engine-test','exec'),env);return env[name]
class User:
 def __init__(self):self.step=0;self.foreground=111;self.installed=[];self.removed=[];self.killed=[]
 def PeekMessageW(self,*a):pass
 def SetWindowsHookExW(self,kind,*a):self.installed.append(kind);return kind+100
 def UnhookWindowsHookEx(self,handle):self.removed.append(handle)
 def SetTimer(self,*a):return 7
 def KillTimer(self,*a):self.killed.append(a)
 def GetForegroundWindow(self):return self.foreground
 def GetMessageW(self,*a):
  if self.step==0:
   assert self.installed==[13];state.update(enabled=True,editing=True,window=111)
  elif self.step==1:
   assert self.installed==[13,14];self.foreground=222
  elif self.step==2:
   assert self.removed==[114];self.foreground=111
  elif self.step==3:
   assert self.installed==[13,14,14];state['enabled']=False
  else:return 0
  self.step+=1;return 1
state={'enabled':False,'editing':False,'window':None};user=User();control={'id':None}
env=dict(C=C,W=W,user=user,kernel=types.SimpleNamespace(GetCurrentThreadId=lambda:42),hook_control=control,hook_ready=threading.Event(),keyboard=object(),mouse=object(),module=1,state=state,stop=threading.Event())
function('hook_worker',env)()
assert user.removed==[114,114,113] and user.killed==[(None,7)] and control['id'] is None
# No mouse callback may acquire the engine lock while the helper is idle or another app is foreground.
class NoLock:
 def __enter__(self):raise AssertionError('Desktop input acquired engine lock')
env=dict(C=C,W=W,state=state,user=types.SimpleNamespace(CallNextHookEx=lambda *a:99,GetForegroundWindow=lambda:222),state_lock=NoLock())
mouse=function('mouse',env);assert mouse(0,0,0)==99
state.update(enabled=True,editing=True,window=111);assert mouse(0,0,0)==99
# Idle capture waits for an event without polling or requesting high-resolution timing.
stop=threading.Event();closed=[]
class Wake:
 def wait(self,*args):assert args==();stop.set()
 def clear(self):pass
class NoTimer:
 def timeBeginPeriod(self,*a):raise AssertionError('Idle high-resolution timer')
env=dict(state={'enabled':False,'editing':False},stop=stop,wake=Wake(),time=__import__('time'),mss=types.SimpleNamespace(MSS=lambda:types.SimpleNamespace(close=lambda:closed.append(True))),winmm=NoTimer())
function('vision_worker',env)();assert closed==[True]
print('PASS: mouse hook absent idle, installed only for edits, removed on focus loss/pause, hook cleanup, desktop input bypass and event-driven idle capture')
# Active scanning requests timing only for the edit, and releases it on shutdown.
stop=threading.Event();timers=[];closed=[]
def rect(*a):stop.set();return False
state={'enabled':True,'editing':True,'window':111,'generation':0}
env=dict(C=C,W=W,state=state,stop=stop,wake=threading.Event(),time=__import__('time'),mss=types.SimpleNamespace(MSS=lambda:types.SimpleNamespace(close=lambda:closed.append(True))),winmm=types.SimpleNamespace(timeBeginPeriod=lambda n:timers.append('begin') or 0,timeEndPeriod=lambda n:timers.append('end')),args=types.SimpleNamespace(scan_hz=360),stats={'actual_hz':0},foreground_game=lambda:111,user=types.SimpleNamespace(IsIconic=lambda hwnd:False,GetClientRect=rect))
function('vision_worker',env)();assert timers==['begin','end'] and closed==[True]
print('PASS: active timer request and release are balanced')
