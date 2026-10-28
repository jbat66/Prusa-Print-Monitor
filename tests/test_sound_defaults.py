from pathlib import Path
import tempfile
import unittest
from sound_defaults import BUNDLED, seed_sounds


class SoundDefaultsTests(unittest.TestCase):
    def test_all_four_sounds_copy_and_existing_files_are_preserved(self):
        names = {'AlarmSoundEffect.mp3', 'ClockChimes.mp3', 'Cuckoo.mp3', 'RedAlert.mp3'}
        self.assertEqual({path.name for path in BUNDLED.glob('*.mp3')}, names)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'sounds'
            seed_sounds(destination)
            self.assertEqual({path.name for path in destination.iterdir()}, names)
            for path in BUNDLED.glob('*.mp3'):
                self.assertEqual((destination / path.name).read_bytes(), path.read_bytes())
            custom = destination / 'AlarmSoundEffect.mp3'
            custom.write_bytes(b'user audio')
            seed_sounds(destination)
            self.assertEqual(custom.read_bytes(), b'user audio')

    def test_legacy_file_mount_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'sounds'
            target.write_bytes(b'existing MP3')
            seed_sounds(target)
            self.assertEqual(target.read_bytes(), b'existing MP3')
