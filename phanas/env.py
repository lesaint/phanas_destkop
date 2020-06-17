import getpass
import sys

from pathlib import Path
from phanas import constants

class Env:
    linux_username = getpass.getuser()
    # from https://stackoverflow.com/a/4028943
    home_dir_path = Path.home()
    # base_mount_dir_path must not be location in /home or /media to not have drive loaded by Nautilus
    # and slow down Gnome's login
    # logical links in /home to mounted drive outside /home are not loaded by Nautilus
    base_mount_dir_path = Path("/" + constants.MOUNT_DIR_NAME)
    mount_dir_path = base_mount_dir_path / linux_username
    # from https://stackoverflow.com/a/31867043
    __script_dir = Path(sys.path[0])
    credential_file_path = Path(__script_dir) / ".phanas"
