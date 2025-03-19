'''
Interfaces to PyAudio and Aubio to handle audio input, output, and manipulation.
'''
from collections import deque
import numpy as np
import pyaudio
import aubio
import math
import os

### Define global audio parameters
# Get the data as signed 32 bit floats
AUDIO_FORMAT = pyaudio.paFloat32
# Use only one channel
NUM_CHANNELS = 1

# Create an enumeration for the audio effects where each value corresponds to a string
class AudioEffect:
    NO_EFFECT = 'No Effect'
    REVERSE = 'Reverse'
    PITCH_SHIFT_UP = 'Pitch Shift Up'
    PITCH_SHIFT_DOWN = 'Pitch Shift Down'
    REVERB = 'Reverb - TBD'
    CRUNCH = 'Crunch - TBD'

# Sample meaning:
# Each sample is a 16-bit signed integer, that tells the speaker how far to move
# in or out. Louder sounds will oscillate more positively and negatively, while
# quieter sounds will oscillate closer to zero.
#
# If samples stayed continually at 2,000 (for example) the speaker would be
# would be silent since it is not moving in or out.

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

def createPitchOffsetStr(noteName, offset):
    '''
    Create a string that will indicate whether the user need to go more flat or
    sharp on the current pitch that is playing. The returned string is always
    the same length, space padded if necessary.
    '''
    # Round the offset to a value between -5 and 5
    rounded_offset = round(offset * 10)
    char_to_use = ">" if rounded_offset < 0 else "<"
    num_chars = abs(rounded_offset)
    max_chars = 5
    if num_chars > max_chars:
        num_chars = max_chars   
    
    offset_str = char_to_use * num_chars

    if rounded_offset < 0:
        return f'{offset_str:>{max_chars}}{noteName}{" " * max_chars}'
    else:
        return f'{" " * max_chars}{noteName}{offset_str:<{max_chars}}'
    

class AudioIO():
    def __init__(self):
        # Initialize PyAudio
        self.recentFrameBuffer = deque(maxlen=(1024 * 16))
        self.pa = pyaudio.PyAudio()

    def __del__(self):
        self.pa.terminate()

    def cyclePyAudioSessions(self):
        '''
        Terminate the PyAudio session and restart it. This allows us to refresh
        the list of input and output devices.
        '''
        self.pa.terminate()
        self.pa = pyaudio.PyAudio()

    def getAudioEffects(self) -> list[str]:
        '''
        Get the list of audio effects

        Returns:
            A list of audio effects
        '''
        return_list = []
        for effect in AudioEffect.__dict__.values():
            if isinstance(effect, str):

                # The name of the file is included in the list of effects so 
                # we need to skip it
                filename = os.path.basename(__file__)
                if effect not in filename:
                    return_list.append(effect)
                    
        return return_list

    def startStreams(self, inputDeviceIdx, OutputDeviceIdx, samplingRateHz,\
                    framesPerBuffer, streamCallback) -> tuple[bool, str]:
        '''
        Start the input and output streams for audio

        Args:
            inputDeviceIdx: The index of the input device to use
            OutputDeviceIdx: The index of the output device to use
            samplingRateHz: The sampling rate in Hz
            framesPerBuffer: The number of frames per buffer

        Returns:
            A tuple containing a boolean indicating success and a string with
            an error message if there was an error.
        '''
         # Open output stream for playback
        try:
            self.outputStream = self.pa.open(format=AUDIO_FORMAT,
                                channels=NUM_CHANNELS,
                                rate=samplingRateHz,
                                output=True,
                                frames_per_buffer=framesPerBuffer,
                                output_device_index=OutputDeviceIdx)
        except OSError as e:
            return False, f'Error opening output stream: {e}'

        # Open input stream for recording
        try:
            self.inputStream = self.pa.open(format=AUDIO_FORMAT,
                                channels=NUM_CHANNELS,
                                rate=samplingRateHz,
                                input=True,
                                frames_per_buffer=framesPerBuffer,
                                input_device_index=inputDeviceIdx,
                                stream_callback=streamCallback)
        except OSError as e:
            return False, f'Error opening input stream: {e}'
        
        # Create aubio pitch detection object
        try:
            # Create a buffer that is 8 times as large as each frame that is 
            # read. This is the maximum size that aubio will accept. It creates
            # the smoothest pitch detection.
            buffer_size = framesPerBuffer * 8
            self.pitchDetector = aubio.pitch('default', buffer_size, \
                framesPerBuffer, samplingRateHz)
            self.pitchDetector.set_unit('Hz')
            self.pitchDetector.set_silence(-40)
        except Exception as e:
            return False, f'Error creating pitch detector: {e}'
        
        return True, ''
    
    def stopStreams(self):
        '''
        Stop the input and output streams
        '''
        if hasattr(self, 'inputStream'):
            self.inputStream.stop_stream()
            self.inputStream.close()
        
        if hasattr(self, 'outputStream'):
            self.outputStream.stop_stream()
            self.outputStream.close()

    def streamCallback(self, inData, frameCount, timeInfo, status, effectStr):
        '''
        Callback function that is called by the PyAudio object when audio data is
        available to be processed. This function is called in a separate thread.
        '''

        # Break out of any error condions
        if status != 0:
            print(f'Error: {status}')
            return (inData, pyaudio.paAbort)
        
        # Convert audio data to numpy array
        audio_data = np.frombuffer(inData, dtype=np.float32)

        
        # Apply the audio effect
        if effectStr == AudioEffect.REVERSE:
            audio_data = audio_data[::-1]
        elif effectStr == AudioEffect.PITCH_SHIFT_UP:
            # First, get an array of every other sample the duplicate the array to 
            # make it the length of the original audio data
            every_other_sample = audio_data[::2]
            audio_data = np.concatenate(
                (every_other_sample, every_other_sample), axis=0)
        elif effectStr == AudioEffect.PITCH_SHIFT_DOWN:
            # Get this first half of the audio data, then duplicate every sample
            # to make the array the length of the original audio data
            first_half = audio_data[:len(audio_data) // 2]
            audio_data = np.concatenate((first_half, first_half), axis=0)
        else:
            pass

        # Get the pitch of the audio data
        # TBD - moving the pitch detection to after the effect is applied to
        #       to see if we are really shifting pitch
        pitch = self.pitchDetector(audio_data)[0]
        note_name, offset = freqToNote(pitch)
        offset_str = createPitchOffsetStr(note_name, offset)

        self.recentFrameBuffer.extend(audio_data)

        # Convert audio data back to bytes
        data = audio_data.tobytes()

        # Write audio data to output stream
        self.outputStream.write(data)

        # Return the audio data and the flag indicating that the callback was successful
        return (offset_str, inData, pyaudio.paContinue)


    def getInputDevices(self) -> tuple[list[str], int]:
        '''
        Get the list of input devices and the index of the default input device

        Returns:
            A tuple containing a list of input devices and the index of the 
            default input device
        '''
        input_devices = []
        for i in range(self.pa.get_device_count()):
            device_info = self.pa.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                input_devices.append(device_info['name'])
        try:
            default_input_device = self.pa.get_default_input_device_info()
            default_input_device_index = default_input_device['index']
        except:
            default_input_device_index = 0
        return input_devices, default_input_device_index
    
    def getOutputDevices(self) -> tuple[list[str], int]:
        '''
        Get the list of output devices and the index of the default output device

        Returns:
            A tuple containing a list of output devices and the index of the 
            default output device
        '''
        output_devices = []
        for i in range(self.pa.get_device_count()):
            device_info = self.pa.get_device_info_by_index(i)
            if device_info['maxOutputChannels'] > 0:
                output_devices.append(device_info['name'])
        try:
            default_output_device = self.pa.get_default_output_device_info()
            default_output_device_index = default_output_device['index']
        except:
            default_output_device_index = 0

        return output_devices, default_output_device_index
