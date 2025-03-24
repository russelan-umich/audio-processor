'''
GUI application that allows the user to select an input and output device, and
then start and stop recording audio from the input device.
'''
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtWidgets import QLabel, QComboBox, QPushButton
import matplotlib.pyplot as plt
from PyQt6.QtCore import Qt
import audio_io as aio

NOT_ACTIVE_STR = '-- Recording not active --'

class AudioApp(QWidget):
    def __init__(self):
        super().__init__()
        self.audioIO = aio.AudioIO()
        self.effectSettings = aio.EffectSettings()
        self.initUI()

    def __del__(self):
        del self.audioIO

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
        '''
        Initialize the user interface for the AudioApp
        '''

        # Create main layout which will be a column of other layouts
        vbox = QVBoxLayout()

        ### Create horizontal layout for dropdown menus with labels
        #
        #
        hbox_top = QHBoxLayout()

        # 1. Input Devices
        input_devices, default_input_device_index = self.audioIO.getInputDevices()
        self.inputComboBox = self.addComboBoxToHBox(hbox_top, \
            'Input Device:', input_devices, default_input_device_index)

        # 2. Output Devices
        output_devices, default_output_device_index = self.audioIO.getOutputDevices()
        self.outputComboBox = self.addComboBoxToHBox(hbox_top, \
            'Output Device:', output_devices, default_output_device_index)

        # 3. Sampling Rate
        # Sample at a rate of 44.1 kHz (44100 samples per second)
        # Standard sampling rate since most humans can hear up to 20 kHz and you 
        # typically want to sample at twice the highest frequency you want to 
        # capture.
        self.samplingRate = self.addComboBoxToHBox(hbox_top, \
            'Sampling Rate (Hz):', ['22050','44100'], default_index=1)

        # 4. Frames Per Buffer
        # Number of frames captured every time the i/o stream are read/written
        self.framesPerBuffer = self.addComboBoxToHBox(hbox_top, \
            'Frames Per Buffer:', ['128','256','512','1024', '2048', '4096', '8192', '16384'], default_index=4)

        vbox.addLayout(hbox_top)


        ### Create horizontal layout for buttons and text display
        #
        #
        hbox_button_row = QHBoxLayout()

        self.startButton = QPushButton('Start')
        self.stopButton = QPushButton('Stop')
        self.refreshButton = QPushButton('Refresh Devices')
        self.plotButton = QPushButton('Create Plot')

        self.startButton.clicked.connect(self.startRecording)
        self.stopButton.clicked.connect(self.stopRecording)
        self.refreshButton.clicked.connect(self.refreshDevices)
        self.plotButton.clicked.connect(self.createPlot)

        hbox_button_row.addWidget(self.startButton)
        hbox_button_row.addWidget(self.stopButton)
        hbox_button_row.addWidget(self.refreshButton)
        hbox_button_row.addWidget(self.plotButton)

        
        vbox.addLayout(hbox_button_row)

        # Create a horizontal layout for the effect tools
        #
        hbox_bottom = QHBoxLayout()

        # Add a selector for which effect to apply
        audio_effects = self.audioIO.getAudioEffects()
        self.appliedEffect = self.addComboBoxToHBox(hbox_bottom, \
            'Effect:', audio_effects, default_index=0)
        
        # Create the tuner display
        tuner_vbox_combo = QVBoxLayout()
        label = QLabel("Tuner")
        tuner_vbox_combo.addWidget(label)
        self.textDisplay = QLabel(NOT_ACTIVE_STR)
        self.textDisplay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tuner_vbox_combo.addWidget(self.textDisplay)
        hbox_bottom.addLayout(tuner_vbox_combo)

        # Add distortion settings
        tuner_vbox_combo = QVBoxLayout()
        label = QLabel("Crunch")
        tuner_vbox_combo.addWidget(label)
        self.textDisplay = QLabel(NOT_ACTIVE_STR)
        self.textDisplay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tuner_vbox_combo.addWidget(self.textDisplay)
        hbox_bottom.addLayout(tuner_vbox_combo)

        vbox.addLayout(hbox_bottom)

        self.setLayout(vbox)

        self.setWindowTitle('Audio Processor')
        self.setGeometry(100, 100, 800, 400)  # Set the window dimensions

    def streamCallback(self, in_data, frame_count, time_info, status):
        '''
        Callback function that is called by the PyAudio object when audio data is
        available to be processed. This function is called in a separate thread.
        '''
        offset_str, in_data, status = \
            self.audioIO.streamCallback(in_data, frame_count, time_info, status, 
                                        self.appliedEffect.currentText(),
                                        self.effectSettings)
        
        self.textDisplay.setText(offset_str)
        return (in_data, status)

    def startRecording(self):
        '''
        Start the recording and playback process
        '''
        # Get the currently selected options
        selected_input_idx = self.inputComboBox.currentIndex()
        selected_output_idx = self.outputComboBox.currentIndex()
        selected_sampling_rate = int(self.samplingRate.currentText())
        selected_frames_per_buffer = int(self.framesPerBuffer.currentText())

        worked, err_str = self.audioIO.startStreams(selected_input_idx, \
                selected_output_idx, selected_sampling_rate, \
                selected_frames_per_buffer, self.streamCallback)
            
        if worked:
            self.inRecordingMode(True)
        else:
            self.textDisplay.setText(err_str)

            

    def stopRecording(self):
        '''
        Stop the recording and playback process
        '''
        self.textDisplay.setText(NOT_ACTIVE_STR)
        self.audioIO.stopStreams()
        self.inRecordingMode(False)

    def inRecordingMode(self, recording: bool):
        '''
        Set the GUI to be in recording mode or not
        '''
        self.inputComboBox.setDisabled(recording)
        self.outputComboBox.setDisabled(recording)
        self.samplingRate.setDisabled(recording)
        self.framesPerBuffer.setDisabled(recording)
        self.startButton.setDisabled(recording)
        self.refreshButton.setDisabled(recording)

    def refreshDevices(self):
        '''
        Refresh the list of input and output devices
        '''
        self.audioIO.cyclePyAudioSessions()

        input_devices, default_input_device_index = self.audioIO.getInputDevices()
        self.inputComboBox.clear()
        for item in input_devices:
            self.inputComboBox.addItem(item)
        self.inputComboBox.setCurrentIndex(default_input_device_index)

        output_devices, default_output_device_index = self.audioIO.getOutputDevices()
        self.outputComboBox.clear()
        for item in output_devices:
            self.outputComboBox.addItem(item)
        self.outputComboBox.setCurrentIndex(default_output_device_index)

    def createPlot(self):
        '''
        Create a plot of the audio data
        '''
        plt.plot(self.audioIO.recentFrameBuffer)
        plt.xlabel('Frame Number')
        plt.show()
