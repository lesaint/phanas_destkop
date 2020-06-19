
import getpass
import os
import phanas.automount
import phanas.file_utils
import phanas.nas
import shutil
import socket
import subprocess
import sys
import tempfile

from datetime import datetime, date, timedelta
from pathlib import Path

class KeePass:
    __KEEPASSXC_CLI="keepassxc-cli"
    __BACKUP_DATE_FORMAT = "%Y-%m-%d"
    __BACKUP_TIMESTAMP_FORMAT = "{}_%H-%M-%S".format(__BACKUP_DATE_FORMAT)
    __BACKUP_EXPIRATION_IN_DAYS = 60

    __automount_env = phanas.automount.Env()
    __nas = phanas.nas.Nas()

    __linux_username = getpass.getuser()
    # see https://stackoverflow.com/a/799799
    __hostname = socket.gethostname()

    # from https://stackoverflow.com/a/31867043
    __script_dir = Path(sys.path[0])
    __credentials_file_path = Path(__script_dir) / ".kpx_phanas"
    __sys_drive_path = __automount_env.mount_dir_path / __nas.drive_sys

    __KEYFILE_DIR_NAME = "keys"
    __keyfile_password = None
    __remote_keyfile_dir_path = None

    __KEYFILE_NAME = "sebastienlesaint.kdbx"
    __remote_keyfile_path = None
    __local_keyfile_path = None

    __keepassxc_cli = None

    def check_prerequisites(self):
        # keepassxc-cli is installed
        self.__keepassxc_cli = shutil.which(self.__KEEPASSXC_CLI)
        if self.__keepassxc_cli is None:
            return False, "{} is not installed".format(self.__KEEPASSXC_CLI)
        print("keepassxc-cli found: {}".format(self.__keepassxc_cli))

        # NAS is online
        status, msg = self.__nas.check_online()
        if not status:
            return False, msg

        # sys drive is mounted
        if not self.__sys_drive_path.is_dir():
            return False, "{} is not a directory".format(self.__sys_drive_path)
        if not os.path.ismount(self.__sys_drive_path):
            return False, "{} is not mounted".format(self.__sys_drive_path)

        status, msg, __keyfile_username, self.__keyfile_password = phanas.file_utils.read_credentials_file(self.__credentials_file_path)
        if not status:
            return False, msg
        print("Keyfile username: {}".format(__keyfile_username))

        self.__remote_keyfile_dir_path = self.__sys_drive_path / self.__KEYFILE_DIR_NAME / __keyfile_username
        self.__remote_keyfile_path = self.__remote_keyfile_dir_path / self.__KEYFILE_NAME
        self.__local_keyfile_path = Path.home() / self.__KEYFILE_NAME

        # remote keyfile dir exists
        if not self.__remote_keyfile_dir_path.is_dir():
            return False, "{} is not a directory".format(self.__remote_keyfile_dir_path)

        # remote keyfile exists
        if not self.__remote_keyfile_path.is_file():
            return False, "{} is not a file".format(self.__remote_keyfile_path)

        # local keyfile exists
        if not self.__local_keyfile_path.is_file():
            return False, "{} is not a file".format(self.__local_keyfile_path)

        return True, None

    def synch_files(self):
        # backup local and remote keyfiles
        status, msg = self.__backup_keyfiles()
        if not status:
            return False, msg

        # create local temp copies of remote file and local file
        with tempfile.NamedTemporaryFile() as local_copy:
            with tempfile.NamedTemporaryFile() as remote_copy:
                shutil.copyfile(self.__local_keyfile_path, local_copy.name)
                shutil.copyfile(self.__remote_keyfile_path, remote_copy.name)

                # sync remote to local and the other way around
                print("merging local keyfile into remote...")
                self.__merge_keyfiles(remote_copy.name, local_copy.name)
                print("merging remote keyfile into local...")
                self.__merge_keyfiles(local_copy.name, remote_copy.name)
                
                # overwrite remote and local with up to date file
                shutil.copy(remote_copy.name, self.__remote_keyfile_path)
                print("{} synchronized".format(self.__remote_keyfile_path))
                shutil.copy(local_copy.name, self.__local_keyfile_path)
                print("{} synchronized".format(self.__local_keyfile_path))

        return True, None

    def __merge_keyfiles(self, into_keyfile, from_keyfile):
        command = [ self.__keepassxc_cli, "merge", "--quiet", "--same-credentials", into_keyfile, from_keyfile ]

        proc = subprocess.Popen(command, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True)
        outs, errs = proc.communicate(input = self.__keyfile_password)
        print("output=" + outs)
        print("errs=" + errs)

    def __backup_keyfiles(self):
        sync_backup_dir_path = self.__remote_keyfile_dir_path / "{backup_dir}/{host}/{linux_user}".format(
            backup_dir = "_sync_backup", host = self.__hostname, linux_user = self.__linux_username)

        status, msg = self.__expire_old_backups(sync_backup_dir_path)
        if not status:
            return False, msg

        # sync backup directory exists or we create it
        for d in [sync_backup_dir_path.parents[1], sync_backup_dir_path.parents[0], sync_backup_dir_path]:
            if not d.exists():
                print("{} does not exists, creating it...".format(d))
                d.mkdir()
            elif not d.is_dir():
                return False, "{} is not a directory".format(d)

        timestamp = datetime.today().strftime(self.__BACKUP_TIMESTAMP_FORMAT)
        remote_keyfile_backup_path = sync_backup_dir_path / "{date}_nas_{keyfilename}".format(date = timestamp, keyfilename = self.__KEYFILE_NAME)
        local_keyfile_backup_path = sync_backup_dir_path / "{date}_local_{keyfilename}".format(date = timestamp, keyfilename = self.__KEYFILE_NAME)
        if remote_keyfile_backup_path.exists() or local_keyfile_backup_path.exists():
            return False, "backup file {} or {} already exists".format(remote_keyfile_backup_path, local_keyfile_backup_path)

        shutil.copyfile(self.__remote_keyfile_path, remote_keyfile_backup_path, follow_symlinks = False)
        shutil.copyfile(self.__local_keyfile_path, local_keyfile_backup_path, follow_symlinks = False)
        phanas.file_utils.make_readonly(remote_keyfile_backup_path)
        phanas.file_utils.make_readonly(local_keyfile_backup_path)

        return True, None

    def __expire_old_backups(self, sync_backup_dir_path):
        if not sync_backup_dir_path.is_dir():
            return True, None

        for file in sync_backup_dir_path.glob("*.kdbx"):
            day_str = file.stem[0:len("2020-06-18")]
            day = datetime.strptime(day_str, self.__BACKUP_DATE_FORMAT)
            threshold_day = datetime.today() - timedelta(days = self.__BACKUP_EXPIRATION_IN_DAYS)
            if day < threshold_day:
                print("deleting old backup {}...".format(file))
                file.unlink()

        return True, None


def run():
    print("Keepass synchronization started")

    keepass = KeePass()
    status, msg = keepass.check_prerequisites()
    if not status:
        print("[ERROR] {}".format(msg))

    status, msg = keepass.synch_files()
    if not status:
        print("[ERROR] {}".format(msg))

    # called after GTK process has ended (ie. window closed and/or Gtk.main_quit is called)
    print("Keepass synchronization done")
