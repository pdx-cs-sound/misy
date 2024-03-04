# misy: Demo MIDI Synthesizer
# Bart Massey 2024

# This very simple synthesizer is intended primarily as a
# demo of MIDI and synthesis. That said, it is a working
# instrument.

import mido, sounddevice
import numpy as np

# Sample rate in sps. This doesn't need to be fixed: it
# could be set to the preferred rate of the audio output.
sample_rate = 48000
# Blocksize in samples to process. My desktop machine keeps
# up at this rate, which provides pretty good latency. Slower
# machines may need larger numbers.
blocksize = 16

# XXX Right now the name of the MIDI controller (keyboard)
# is hard-coded.  This should be fixed somehow. You can use
# the commented-out line instead to create an instrument
# (synth) that you can connect a controller to using your
# system mechanism.
#
# keyboard = mido.open_input('fmlite', virtual=True)
keyboard = mido.open_input('USB Oxygen 8 v2 MIDI 1')

# XXX Right now, 0 to output sine waves and 1 to output square waves.
# This needs much work.
out_osc = 0

# Dictionary of currently playing notes, indexed by MIDI key
# number.
out_keys = dict()

# Set true to get a printed log message every time a key is
# pressed or released. Usually more annoying that useful.
log_notes = False

# Attack time in seconds.
#
# XXX This is the uncompleted beginning of an ADSR envelope
# implementation.
attack_time = 0.020

# This count of the number of samples output so far is
# used to make sure that waveforms are generated with
# the right phase.
#
# It would be great if Python provided nonlocal variables
# with static initialization. It does not.
sample_clock = 0

# Representation of a note currently being played.
class Note:
    def __init__(self, key, osc):
        self.frequency = key_to_freq(key)
        self.attack_time_remaining = attack_time
        self.out_osc = osc
        self.playing = True

    # Note has been released.
    def release(self):
        self.playing = False

    # Accept a time linspace to generate samples in.  Return
    # that many samples of note being played, or None if
    # note is over.
    def samples(self, t):
        if not self.playing:
            return None

        frame_count = len(t)
        out_frequency = self.frequency

        # Pick and generate a waveform.
        if self.out_osc == 0:
            samples = np.sin(2 * np.pi * out_frequency * t, dtype=np.float32)
        elif self.out_osc == 1:
            samples = (out_frequency * t) % 2.0 - 1.0
        else:
            assert False

        # Do attack part of ADSR envelope.
        attack_time_remaining = self.attack_time_remaining
        if attack_time_remaining > 0.0:
            # Figure out the gain at the starting time according
            # to a linear ramp.
            start_gain = 1.0 - attack_time_remaining / attack_time
            # Figure out the time after the last sample, and
            # adjust the attack_time_remaining to reflect it.
            end_time = frame_count / sample_rate
            attack_time_remaining -= end_time
            # Figure out the gain at the ending time according
            # to a linear ramp.
            end_gain = 1.0 - attack_time_remaining / attack_time
            # Calculate the linear slope over the samples. Make
            # sure it doesn't go above 1.0 due to finishing the
            # attack in the middle.
            #
            # XXX This should probably be linear in dBFS rather than
            # linear in amplitude, but meh.
            envelope = np.clip(
                np.linspace(start_gain, end_gain, frame_count),
                0.0,
                1.0,
            )
            # Apply the per-sample gains for the attack.
            samples *= envelope
            # Update the attack time remaining for next pass.
            self.attack_time_remaining = attack_time_remaining

        return samples

# This callback is called by `sounddevice` to get some
# samples to output. It's the heart of sound generation in
# the synth.
def output_callback(out_data, frame_count, time_info, status):
    # Make sure to update the *global* sample clock.
    global sample_clock

    # A non-None status indicates that something has
    # happened with sound output that shouldn't have.  This
    # is almost always an underrun due to generating samples
    # too slowly.
    if status:
        print("output callback:", status)

    # Start with silence and maybe work up.
    samples = np.zeros(frame_count, dtype=np.float32)

    # If keys are pressed, generate sounds.
    if out_keys:
        # Time point in seconds for each sample.
        t = np.linspace(
            sample_clock / sample_rate,
            (sample_clock + frame_count) / sample_rate,
            frame_count,
            dtype=np.float32,
        )
        # Set of keys that are done playing and need to be
        # deleted.
        on_keys = list(out_keys.keys())
        del_keys = set()
        # Generate the samples for each key and add them
        # into the mix.
        for key in on_keys:
            note = out_keys[key]
            note_samples = note.samples(t)
            if note_samples is None:
                del_keys.add(key)
                continue
            samples += note_samples
        # Close the deleted keys.
        for key in del_keys:
            del out_keys[key]

    # Adjust the gain so that each key gets louder up to
    # some maximum.  If necessary, scale to avoid clipping.
    nkeys = len(out_keys)
    if nkeys <= 8:
        samples *= 1.0 / 8.0
    else:
        samples *= 1.0 / len(out_keys)

    # Reshape to have an array of 1 sample for each frame.
    # Must write into the existing array rather than
    # accidentally copying over the parameter.
    out_data[:] = np.reshape(samples, (frame_count, 1))

    # Bump the sample clock for next cycle.
    sample_clock += frame_count

# Calculate frequency for a 12-tone equal-tempered Western
# scale given MIDI note number. Change 440 to 432 for better
# sound </s>.
def key_to_freq(key):
    return 440 * 2 ** ((key - 69) / 12)

# Block waiting for the instrument (keyboard) to send a MIDI
# message, then handle it. Return False if the MIDI message
# wants the synthesizer to stop, True otherwise.
def process_midi_event():
    # These globals define the interface to sound generation.
    global out_keys, out_osc

    # Block until a MIDI message is received.
    mesg = keyboard.receive()

    # Select what to do based on message type.
    mesg_type = mesg.type
    # Special case: note on with velocity 0 indicates
    # note off (for older MIDI instruments).
    if mesg_type == 'note_on' and mesg.velocity == 0:
        mesg_type = 'note_off'
    # Add a note to the sound. If it is already on just
    # start it again.
    if mesg_type == 'note_on':
        key = mesg.note
        velocity = mesg.velocity / 127
        if log_notes:
            print('note on', key, mesg.velocity, round(velocity, 2))
        out_keys[key] = Note(key, out_osc)
    # Remove a note from the sound. If it is already off,
    # this message will be ignored.
    elif mesg_type == 'note_off':
        key = mesg.note
        velocity = round(mesg.velocity / 127, 2)
        if log_notes:
            print('note off', key, mesg.velocity, velocity)
        if key in out_keys:
            out_keys[key].release()
    # Handle various controls.
    elif mesg.type == 'control_change':
        # XXX Hard-wired for "stop" key on Oxygen8.
        if mesg.control == 23:
            print('stop')
            return False
        # Change output waveform.
        #
        # XXX Hard-wired for "fast-forward" and "reverse"
        # keys on Oxygen8. Hard-coded for exactly two possible
        # waveforms.
        elif mesg.control == 21 or mesg.control == 22:
            print('program change')
            out_osc = (out_osc + 1) % 2
        # Unknown control changes are logged and ignored.
        else:
            print(f"control", mesg.control, mesg.value)
    # XXX Pitchwheel is currently logged and ignored.
    elif mesg.type == 'pitchwheel':
        pitch = round(mesg.pitch / 127, 2)
        print('pitchwheel', mesg.pitch, pitch)
    else:
        print('unknown MIDI message', mesg)
    return True


# Start audio playing. Must keep up with output from here on.
output_stream = sounddevice.OutputStream(
    samplerate=sample_rate,
    channels=1,
    blocksize=blocksize,
    callback=output_callback,
)
output_stream.start()

# Run the synthesizer until its stop key is pressed.
while process_midi_event():
    pass
