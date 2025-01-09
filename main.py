from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtWidgets import QLabel, QComboBox, QPushButton
import matplotlib.pyplot as plt
import numpy as np
import pyaudio
import aubio
import math
import sys

# Initialize PyAudio
pa = pyaudio.PyAudio()

### Define global audio parameters
# Get the data as 16-bit signed integers
AUDIO_FORMAT = pyaudio.paFloat32
# Use only one channel
NUM_CHANNELS = 1

NOT_ACTIVE_STR = '-- Recording not active --'

# Sample meaning:
# Each sample is a 16-bit signed integer, that tells the speaker how far to move
# in or out. Louder sounds will oscillate more positively and negatively, while
# quieter sounds will oscillate closer to zero.
#
# If samples stayed continually at 2,000 (for example) the speaker would be
# would be silent since it is not moving in or out.

# TBD Setup refresh button for audio devices
# TBD When we get to the point of trying to tune:

# TBD Need to figure out why the program stops when start is called a second time
# TBD It might be useful at some point to see get_input_latency() and get_output_latency()


def freqToNote(freqHz: float) -> tuple[str, float]:
    '''
    Convert a frequency to a note and let you know how off you are from the note.

    Derived  from:
    https://en.wikipedia.org/wiki/Piano_key_frequencies
    https://stackoverflow.com/questions/64505024/turning-frequencies-into-notes-in-python

    Args:
        freqHz: The frequency in Hz

    Returns:
        A tuple containing the note and the difference from the note on a 
        relative scale from -0.5 to 0.5. 
    '''
    notes = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#']

    freq_hz_of_a4 = 440
    # There are 12 semitones in an each octave (A, A#, ..., G#)
    num_semitones = 12
    # A4 is the 1st note of fifth octave (they start counting octaves from 0)
    note_num_of_a4 = 49
   
    # Make sure freqHz is valid before running
    if freqHz <= 0:
        return 'Invalid', 0
    note_number = num_semitones * math.log2(freqHz / freq_hz_of_a4) + note_num_of_a4  

    # Figure out which note and octave we are closest to 
    rounded_note_number = round(note_number)    
    note = (rounded_note_number - 1 ) % len(notes)
    note_name = notes[note]
    octave = (rounded_note_number + 8 ) // len(notes)

    # Get the return values
    full_note = f'{note_name}{octave}'
    diff = note_number - rounded_note_number
    
    return full_note, diff

class AudioApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def __del__(self):
        pa.terminate()

    def streamCallback(self, in_data, frame_count, time_info, status):
        '''
        Callback function that is called by the PyAudio object when audio data is
        available to be processed. This function is called in a separate thread.
        '''

        # Break out of any error condions
        if status != 0:
            print(f'Error: {status}')
            return (in_data, pyaudio.paAbort)
        
        # Convert audio data to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.float32)

        # Get the pitch of the audio data
        pitch = self.pitchDetector(audio_data)[0]
        confidence = self.pitchDetector.get_confidence()

        note_name, offset = freqToNote(pitch)
        self.textDisplay.setText(f'Pitch: {pitch:.2f} Hz, Confidence: '\
            f'{confidence:.2f}\nNote: {note_name}, Offset: {offset:.2f}')

        # Convert audio data back to bytes
        data = audio_data.tobytes()

        # Write audio data to output stream
        self.outputStream.write(data)

        # Return the audio data and the flag indicating that the callback was successful
        return (in_data, pyaudio.paContinue)

    def addComboBoxToHBox(self, hbox: QHBoxLayout, label_text: str, items: list,\
                          default_index: int) -> QComboBox:
        '''
        Add a dropdown menu to the horizontal layout hbox with the given label_text
        and items. The default_index is the index of the item that should be
        selected by default.
        '''
        label = QLabel(label_text)
        combo_box = QComboBox()
        for item in items:
            combo_box.addItem(item)
        combo_box.setCurrentIndex(default_index)

        vbox_combo = QVBoxLayout()
        vbox_combo.addWidget(label)
        vbox_combo.addWidget(combo_box)
        hbox.addLayout(vbox_combo)

        return combo_box


    def initUI(self):
        # Create main layout
        vbox = QVBoxLayout()

        # Create horizontal layout for dropdown menus with labels
        hbox_top = QHBoxLayout()

        # 1. Input Devices
        input_devices = []
        for i in range(pa.get_device_count()):
            device_info = pa.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                input_devices.append(device_info['name'])
        try:
            default_input_device = pa.get_default_input_device_info()
            default_input_device_index = default_input_device['index']
        except:
            default_input_device_index = 0
        self.inputComboBox = self.addComboBoxToHBox(hbox_top, \
            'Input Device:', input_devices, default_input_device_index)

        # 2. Output Devices
        output_devices = []
        for i in range(pa.get_device_count()):
            device_info = pa.get_device_info_by_index(i)
            if device_info['maxOutputChannels'] > 0:
                output_devices.append(device_info['name'])
        try:
            default_output_device = pa.get_default_output_device_info()
            default_output_device_index = default_output_device['index']
        except:
            default_output_device_index = 0
        self.outputComboBox = self.addComboBoxToHBox(hbox_top, \
            'Output Device:', output_devices, default_output_device_index)

        # 3. Sampling Rate
        # Sample at a rate of 44.1 kHz (44100 samples per second)
        # Standard sampling rate since most humans can hear up to 20 kHz and you 
        # typically want to sample at twice the highest frequency you want to 
        # capture.
        self.samplingRate = self.addComboBoxToHBox(hbox_top, \
            'Sampling Rate (Hz):', ['44100'], default_index=0)

        # 4. Frames Per Buffer
        # Number of frames captured every time the i/o stream are read/written
        self.framesPerBuffer = self.addComboBoxToHBox(hbox_top, \
            'Frames Per Buffer:', ['1024', '2048', '4096'], default_index=1)

        vbox.addLayout(hbox_top)

        # Create horizontal layout for buttons and text display
        hbox_bottom = QHBoxLayout()

        start_button = QPushButton('Start')
        stop_button = QPushButton('Stop')
        self.textDisplay = QLabel(NOT_ACTIVE_STR)

        start_button.clicked.connect(self.startRecording)
        stop_button.clicked.connect(self.stopRecording)

        hbox_bottom.addWidget(start_button)
        hbox_bottom.addWidget(stop_button)
        hbox_bottom.addWidget(self.textDisplay)

        vbox.addLayout(hbox_bottom)

        self.setLayout(vbox)

        self.setWindowTitle('Audio Processor')
        self.setGeometry(100, 100, 800, 400)  # Set the window dimensions

    def startRecording(self):
        '''
        Start the recording and playback process
        '''
        self.textDisplay.setText("Recording and playing back...")

        # Get the currently selected options
        selected_input_idx = self.inputComboBox.currentIndex()
        selected_output_idx = self.outputComboBox.currentIndex()
        selected_sampling_rate = int(self.samplingRate.currentText())
        selected_frames_per_buffer = int(self.framesPerBuffer.currentText())

        # Open output stream for playback
        try:
            self.outputStream = pa.open(format=AUDIO_FORMAT,
                                channels=NUM_CHANNELS,
                                rate=selected_sampling_rate,
                                output=True,
                                frames_per_buffer=selected_frames_per_buffer,
                                output_device_index=selected_output_idx)
        except OSError as e:
            self.textDisplay.setText(f'Error opening output stream: {e}')
            return

        # Open input stream for recording
        try:
            self.inputStream = pa.open(format=AUDIO_FORMAT,
                                channels=NUM_CHANNELS,
                                rate=selected_sampling_rate,
                                input=True,
                                frames_per_buffer=selected_frames_per_buffer,
                                input_device_index=selected_input_idx,
                                stream_callback=self.streamCallback)
        except OSError as e:
            self.textDisplay.setText(f'Error opening input stream: {e}')
            return
        
        # Create aubio pitch detection object
        try:
            # Create a buffer that is 8 times as large as each frame that is 
            # read. This is the maximum size that aubio will accept. It creates
            # the smoothest pitch detection.
            buffer_size = selected_frames_per_buffer * 8
            self.pitchDetector = aubio.pitch('default', \
                buffer_size, selected_frames_per_buffer,
                selected_sampling_rate)
            self.pitchDetector.set_unit('Hz')
            self.pitchDetector.set_silence(-40)
        except Exception as e:
            print(f'Error creating pitch detector: {e}')
            self.textDisplay.setText(f'Error creating pitch detector: {e}')
            return

    def stopRecording(self):
        '''
        Stop the recording and playback process
        '''
        self.textDisplay.setText(NOT_ACTIVE_STR)

        # Close streams and terminate PyAudio
        if hasattr(self, 'inputStream'): 
            self.inputStream.stop_stream()
            self.inputStream.close()

        if hasattr(self, 'outputStream'):
            self.outputStream.stop_stream()
            self.outputStream.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = AudioApp()
    ex.show()
    sys.exit(app.exec())