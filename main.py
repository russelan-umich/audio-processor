import matplotlib.pyplot as plt
import numpy as np
import pyaudio

# Initialize PyAudio
p = pyaudio.PyAudio()

### Define audio parameters
# Get the data as 16-bit signed integers
AUDIO_FORMAT = pyaudio.paInt16
# Use only one channel
NUM_CHANNELS = 1
# Sample at a rate of 44.1 kHz (44100 samples per second)
# Standard sampling rate since most humans can hear up to 20 kHz and you 
# typically want to sample at twice the highest frequency you want to capture.
SAMPLING_RATE_HZ = 44100
# Read and write 1,024 samples at a time
FRAMES_PER_BUFFER = 1024

# Sample meaning:
# Each sample is a 16-bit signed integer, that tells the speaker how far to move
# in or out. Louder sounds will oscillate more positively and negatively, while
# quieter sounds will oscillate closer to zero.
#
# If samples stayed continually at 2,000 (for example) the speaker would be
# would be silent since it is not moving in or out.

# TBD Figure out how to select the input and output devices
# -- Can use input_device_index and output_device_index to select the input and 
#    output devices (need to know the device index)
# TBD get_default_input_device_info() and get_default_output_device_info() might be useful
#       Looks like they reutrn a dictionary
# TBD it might be useful at some point to see get_input_latency() and get_output_latency()


# Open input stream for recording
input_stream = p.open(format=AUDIO_FORMAT,
                      channels=NUM_CHANNELS,
                      rate=SAMPLING_RATE_HZ,
                      input=True,
                      frames_per_buffer=FRAMES_PER_BUFFER)

# Open output stream for playback
output_stream = p.open(format=AUDIO_FORMAT,
                       channels=NUM_CHANNELS,
                       rate=SAMPLING_RATE_HZ,
                       output=True,
                       frames_per_buffer=FRAMES_PER_BUFFER)

print("Recording and playing back...")

# Create an array to store audio data
record_length = 300
full_recording = np.zeros(FRAMES_PER_BUFFER*record_length, dtype=np.int16)


for i in range(record_length):
    try:
        # Read audio data from input stream
        data = input_stream.read(FRAMES_PER_BUFFER)

        # Convert audio data to numpy array
        audio_data = np.frombuffer(data, dtype=np.int16)

        # Process audio data here (e.g., apply effects)
        # ...

        # Store audio data into full_recording
        full_recording[i*FRAMES_PER_BUFFER:(i+1)*FRAMES_PER_BUFFER] = audio_data

        # Convert audio data back to bytes
        #data = audio_data.tobytes()

        # Write audio data to output stream
        #output_stream.write(data)

    except KeyboardInterrupt:
        print("*** Ctrl+C pressed, exiting")
        break

# Close streams and terminate PyAudio
input_stream.stop_stream()
input_stream.close()
output_stream.stop_stream()
output_stream.close()
p.terminate()

# Plot the recorded audio data
plt.plot(full_recording)
plt.xlabel('Sample')
plt.ylabel('Amplitude (16-bit)')
plt.show()
