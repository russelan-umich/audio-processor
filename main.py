'''
Start up the AudioApp 
'''
from PyQt6.QtWidgets import QApplication
from audio_app import AudioApp
import sys

# TBDS:
# - Add volume knob
# - Crunch/Tremelo effect dynamics
# - Move time_since_last_tremelo out of global variable
# - Massive reafactor to make this easier to follow
# - Add tremelo depth
# - It might be useful at some point to see get_input_latency() and 
# get_output_latency() from PyAudio

if __name__ == '__main__':   
    app = QApplication(sys.argv)
    ex = AudioApp()
    ex.show()
    sys.exit(app.exec())