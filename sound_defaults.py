"""Seed bundled alerts without replacing user-provided files."""
import logging
from pathlib import Path
import shutil

LOG = logging.getLogger('Prusa-Print-Monitor.log')
BUNDLED = Path(__file__).parent / 'assets' / 'sounds'


def seed_sounds(destination, source=BUNDLED):
    destination = Path(destination)
    if destination.is_file():
        LOG.warning('Legacy single-file /sounds mount detected; bundled sounds cannot be copied to the host until a folder is mounted')
        return
    destination.mkdir(parents=True, exist_ok=True)
    for sound in sorted(source.glob('*.mp3')):
        target = destination / sound.name
        try:
            with target.open('xb') as output:
                with sound.open('rb') as input_file:
                    shutil.copyfileobj(input_file, output)
            target.chmod(0o644)
            LOG.info('Installed bundled sound: %s', sound.name)
        except FileExistsError:
            LOG.info('Preserving existing sound: %s', sound.name)
