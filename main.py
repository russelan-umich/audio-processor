'''
Start up the AudioApp 
'''
from PyQt6.QtWidgets import QApplication
from audio_app import AudioApp
import sys

# TBD Need to figure out why the program stops when start is called a second time
# TBD It might be useful at some point to see get_input_latency() and 
# get_output_latency() from PyAudio

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AudioApp()
    ex.show()
    sys.exit(app.exec())