from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.lang import Builder
from spectrometer import pyCCDGUI

# Load the Kivy language file for the main screen
Builder.load_file('src/ui/main_screen.kv')

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        # Initialize the spectrometer functionality
        self.spectrometer = pyCCDGUI.Spectrometer()

    def start_spectrometer(self):
        # Call the method to start the spectrometer
        self.spectrometer.start()

class MyApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainScreen(name='main'))
        return sm

if __name__ == '__main__':
    MyApp().run()