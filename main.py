'''
Start up the AudioApp 
'''
from PyQt6.QtWidgets import QApplication
from audio_app import AudioApp
import sys

# TBDS:
# - Add volume knob
# - Get access to sample rate inside audio_io
# - Use distortion pedal to see what is looks like
# - It might be useful at some point to see get_input_latency() and 
# get_output_latency() from PyAudio

if __name__ == '__main__':   
    app = QApplication(sys.argv)
    ex = AudioApp()
    ex.show()
    sys.exit(app.exec())