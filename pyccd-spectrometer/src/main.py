from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from spectrometer.pyCCDGUI import main as pyCCDGUI_main

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        # Initialize the spectrometer functionality
        pyCCDGUI_main()

class MyApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

if __name__ == "__main__":
    MyApp().run()