# misy: toy MIDI synthesizer in Python
Bart Massey 2024

This toy synthesizer is intended to teach basics of
synthesizer-building: it is quite simple, but still usable.

Some of the code is adapted from my teaching synthesizer
[`fm`](https://github.com/pdx-cs-sound/fm).

## Notes

Note that that `mido` used by this will not work with
`rtmidi`: you need `python-rtmidi`. There's a
`requirements.txt` file.

The controller name is currently hard-coded. You will likely
want to change that.

## License

This work is licensed under the "MIT License". Please see the file
`LICENSE.txt` in this distribution for license terms.
