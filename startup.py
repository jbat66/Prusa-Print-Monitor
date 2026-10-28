"""Populate the host sound folder, then run the dashboard unprivileged."""
import logging
import os
from pathlib import Path
import sys
from sound_defaults import seed_sounds


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    seed_sounds(Path('/sounds'))
    if os.name == 'posix' and os.getuid() == 0:
        import pwd
        account = pwd.getpwnam('monitor')
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    command = sys.argv[1:] or [sys.executable, '-u', 'app.py']
    os.execvp(command[0], command)
