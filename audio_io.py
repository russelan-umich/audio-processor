'''
Interfaces to PyAudio and Aubio to handle audio input, output, and manipulation.
'''
from scipy.signal import correlate
from scipy.signal import square
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
# What to display when the pitch is unable to be computed
INVALID_STR = 'Invalid'

# Create an enumeration for the audio effects where each value corresponds to a string
class AudioEffect:
    NO_EFFECT = 'No Effect'
    CRUNCH = 'Crunch'
    SQUARE = 'Square'
    TREMOLO = 'Tremolo'

class EffectSettings:
    def __init__(self):
        # Default effect settings
        self.tremelo_frame_length = 4096
        self.tremelo_frames_to_scale = 10
        self.crunch_threshold = 0.3
        self.crunch_gain = 20

# This value will have the range of -1 * TREMELO_FRAME_LENGTH to TREMELO_FRAME_LENGTH
# It will be used to keep track of how many samples have been processed since the last
# tremelo effect. If the value is less than TREMELO_FRAME_LENGTH, then the effect will
# be applied. If the value is greater than TREMELO_FRAME_LENGTH, then the effect will
# not be applied.
time_since_last_tremelo = 0


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
        return INVALID_STR, 0
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
        
        # Save the sampling rate in Hz
        self.samplingRateHz = samplingRateHz
        
        # Create aubio pitch detection object
        try:
            # Create a buffer that is 8 times as large as each frame that is 
            # read. This is the maximum size that aubio will accept. It creates
            # the smoothest pitch detection.
            buffer_size = framesPerBuffer * 2
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

    def streamCallback(self, inData, frameCount, timeInfo, status, effectStr,
                       effectSettings) -> tuple[str, bytes, int]:
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

        # Get the pitch of the audio data up front before manipulations
        pitch = self.pitchDetector(audio_data)[0]
        note_name, offset = freqToNote(pitch)
        offset_str = createPitchOffsetStr(note_name, offset)

        if len(self.recentFrameBuffer) > 0:
            prev_last_frame = self.recentFrameBuffer[-1]
            prev_last_frame_going_up = self.recentFrameBuffer[-1] > self.recentFrameBuffer[-2]
        else:
            prev_last_frame = 0
            prev_last_frame_going_up = True

        # Apply the audio effect
        if effectStr == AudioEffect.CRUNCH:
            # Apply gain
            crunch_gain = float(effectSettings.crunch_gain)
            effect_data = audio_data * crunch_gain

            # Clip audio to simulate distortion (crunchy effect)
            effect_data = np.clip(effect_data, -effectSettings.crunch_threshold, \
                                  effectSettings.crunch_threshold)

            # Normalize back to original range
            effect_data = effect_data / crunch_gain

            audio_data = np.array(effect_data, dtype=np.float32)
            
        elif effectStr == AudioEffect.TREMOLO:

            global time_since_last_tremelo

            effect_data = audio_data.copy()

            frame_length = effectSettings.tremelo_frame_length
            frames_to_scale = effectSettings.tremelo_frames_to_scale

            # Set samples to 0 if we should be dropping the sample to create a 
            # tremelo effect. IF we are coming in or going out of the samples
            # that we drop then we scale the samples to create a smooth effect
            for i in range(len(effect_data)):
                if time_since_last_tremelo < 0:
                    effect_data[i] = 0
                elif time_since_last_tremelo < frames_to_scale:
                    effect_data[i] = audio_data[i] * (time_since_last_tremelo / frames_to_scale)
                elif time_since_last_tremelo > (frame_length - frames_to_scale):
                    effect_data[i] = audio_data[i] * \
                        ((frame_length - time_since_last_tremelo) / frames_to_scale)
                else:
                    effect_data[i] = audio_data[i]
                time_since_last_tremelo += 1

                # Reset the time since last tremelo if it is greater than the frame length
                if time_since_last_tremelo >= frame_length:
                    time_since_last_tremelo = -1 * frame_length
                
            audio_data = np.array(effect_data, dtype=np.float32)

        elif effectStr == AudioEffect.SQUARE:

            if pitch == 0:
                # If the pitch is 0, then we can't generate a sawtooth wave
                # so we just return the audio data as is
                audio_data = np.zeros_like(audio_data)
                return (INVALID_STR, inData, pyaudio.paContinue)
            
            # Make it twice as long as the audio data so we have a buffer to 
            # crop later on
            duration = (audio_data.shape[0] * 2) / self.samplingRateHz
            t = np.linspace(0, duration, audio_data.shape[0] * 2, endpoint=False)
            effect_wave = square(2 * np.pi * pitch * t, 0.5)

            # Use the amplitude of the audio data to scale the square wave.
            # The square wave has quite a bit more prescence than the audio data
            # so we scale it down by a factor
            scale_factor = 0.1
            scaled_min = audio_data.min() * scale_factor
            scaled_max = audio_data.max() * scale_factor
            effect_wave = np.interp(effect_wave, (-1, 1), (scaled_min, scaled_max))

            # Convert to 32 bit floats
            effect_wave = np.array(effect_wave, dtype=np.float32)

            # Find the index in the first half of the square wave that is 
            # closest to the last frame of the audio data and is also going
            # in the same direction as the last frame of the audio data
            min_diff = np.inf
            min_diff_idx = 0
            end_idx = (len(effect_wave) // 2) - 1
            for i in range(end_idx):
                going_up = effect_wave[i] > effect_wave[i-1]
                diff = abs(effect_wave[i] - prev_last_frame)

                if diff < min_diff and going_up == prev_last_frame_going_up:
                    min_diff = diff
                    min_diff_idx = i
            
            # Crop the square wave to start at the min_diff_idx and end at
            # the length of the audio_data
            start_idx = min_diff_idx + 1
            audio_data = effect_wave[start_idx:start_idx + len(audio_data)]
        else:
            pass

        

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
