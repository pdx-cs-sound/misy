import mido, sounddevice
import numpy as np

samplerate = 48000
blocksize = 1024

# keyboard = mido.open_input('fmlite', virtual=True)
keyboard = mido.open_input('USB Oxygen 8 v2 MIDI 1')

sample_clock = 0
out_key = None
out_frequency = None

def output_callback(out_data, frame_count, time_info, status):
    global sample_clock

    if status:
        print("ocb", status)

    if out_frequency:
        t = np.linspace(
            sample_clock / samplerate,
            (sample_clock + frame_count) / samplerate,
            frame_count,
            dtype=np.float32,
        )
        samples = np.sin(2 * np.pi * out_frequency * t, dtype=np.float32)
    else:
        samples = np.zeros(frame_count, dtype=np.float32)
    # Reshape to have an array of 1 sample for each frame.
    out_data[:] = np.reshape(samples, (frame_count, 1))

    sample_clock += frame_count

output_stream = sounddevice.OutputStream(
    samplerate=samplerate,
    channels=1,
    blocksize=blocksize,
    callback=output_callback,
)
output_stream.start()

def key_to_freq(key):
    return 440 * 2 ** ((key - 69) / 12)

def process_midi_event():
    global out_key, out_frequency

    mesg = keyboard.receive()
    mesg_type = mesg.type
    if mesg_type == 'note_on' and mesg.velocity == 0:
        mesg_type = 'note_off'
    if mesg_type == 'note_on':
        key = mesg.note
        velocity = mesg.velocity / 127
        print('note on', key, mesg.velocity, round(velocity, 2))
        out_key = key
        out_frequency = key_to_freq(key)
    elif mesg_type == 'note_off':
        key = mesg.note
        velocity = round(mesg.velocity / 127, 2)
        print('note off', key, mesg.velocity, velocity)
        if key == out_key:
            out_key = None
            out_frequency = None
    elif mesg.type == 'control_change':
        if mesg.control == 23:
            print('stop')
            return False
        else:
            print(f"control", mesg.control, mesg.value)
    elif mesg.type == 'pitchwheel':
        pitch = round(mesg.pitch / 127, 2)
        print('pitchwheel', mesg.pitch, pitch)
    else:
        assert False, f'unknown message {mesg}'
    return True

while process_midi_event():
    pass
