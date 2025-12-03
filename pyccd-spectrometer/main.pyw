import os
import sys
import subprocess

# ensure repository root is on sys.path so modules can be found
_here = os.path.dirname(__file__)
_repo_root = os.path.abspath(os.path.join(_here, ".."))
sys.path.insert(0, _repo_root)

def start_spectrometer_subprocess():
    env = os.environ.copy()
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _repo_root + (os.pathsep + prev if prev else "")
    # run the spectrometer GUI as a separate process to avoid Tk / Kivy conflicts
    try:
        subprocess.Popen([sys.executable, "-m", "spectrometer.pyCCDGUI"], env=env)
    except Exception as e:
        # print minimal error so you can paste it if it fails
        print("Failed to start spectrometer subprocess:", e, file=sys.stderr)

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.core.window import Window

# simulate horizontal medium phone layout while testing on mac (adjust as needed)
Window.size = (800, 400)

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        # start the original spectrometer GUI in its own process (keeps functionality)
        start_spectrometer_subprocess()
        self.add_widget(Label(text="Spectrometer GUI started in subprocess", halign='center'))

class MyApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

if __name__ == "__main__":
    MyApp().run()