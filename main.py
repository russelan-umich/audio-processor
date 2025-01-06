import pyaudio
import numpy as np

# Initialize PyAudio
p = pyaudio.PyAudio()

# Define audio parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024

# Open input stream for recording
input_stream = p.open(format=FORMAT,
                      channels=CHANNELS,
                      rate=RATE,
                      input=True,
                      frames_per_buffer=CHUNK)

# Open output stream for playback
output_stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       output=True,
                       frames_per_buffer=CHUNK)

print("Recording and playing back...")


# Loop 1,000 times
for _ in range(10000):
    # Read audio data from input stream
    data = input_stream.read(CHUNK)

    # Convert audio data to numpy array
    audio_data = np.frombuffer(data, dtype=np.int16)

    # Process audio data here (e.g., apply effects)
    # ...

    # Convert audio data back to bytes
    data = audio_data.tobytes()

    # Write audio data to output stream
    output_stream.write(data)

# Close streams and terminate PyAudio
input_stream.stop_stream()
input_stream.close()
output_stream.stop_stream()
output_stream.close()
p.terminate()