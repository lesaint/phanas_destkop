
import getpass
import os
import phanas.automount
import phanas.nas
import shutil
import socket
import stat
import subprocess
import tempfile

from datetime import datetime, date, timedelta
from pathlib import Path

class KeePass:
    __KEEPASSXC_CLI="keepassxc-cli"
    __BACKUP_DATE_FORMAT = "%Y-%m-%d"
    __BACKUP_TIMESTAMP_FORMAT = "{}_%H-%M-%S".format(__BACKUP_DATE_FORMAT)
    __BACKUP_EXPIRATION_IN_DAYS = 60

    __automount_env = phanas.automount.Env()

    __linux_username = getpass.getuser()
    # see https://stackoverflow.com/a/799799
    __hostname = socket.gethostname()

    __sys_drive_path = __automount_env.mount_dir_path / "sys"

    __KEYFILE_DIR_NAME = "keys"
    __nas_username = "phan" ## FIXME username must not be hardcoded
    __remote_keyfile_dir_path = __sys_drive_path / __KEYFILE_DIR_NAME / __nas_username

    __KEYFILE_NAME = "sebastienlesaint.kdbx"
    __remote_keyfile_path = __remote_keyfile_dir_path / __KEYFILE_NAME
    __local_keyfile_path = Path.home() / __KEYFILE_NAME

    __keepassxc_cli = None

    def check_prerequisites(self):
        # keepassxc-cli is installed
        self.__keepassxc_cli = shutil.which(self.__KEEPASSXC_CLI)
        if self.__keepassxc_cli is None:
            return False, "{} is not installed".format(self.__KEEPASSXC_CLI)
        print("keepassxc-cli found: {}".format(self.__keepassxc_cli))

        # NAS is online
        nas = phanas.nas.Nas()
        status, msg = nas.check_online()
        if not status:
            return False, msg

        # sys drive is mounted
        if not self.__sys_drive_path.is_dir():
            return False, "{} is not a directory".format(self.__sys_drive_path)
        if not os.path.ismount(self.__sys_drive_path):
            return False, "{} is not mounted".format(self.__sys_drive_path)

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

                keyfile_password = self.__ask_for_keyfile_password()
                # sync remote to local and the other way around
                print("merging local keyfile into remote...")
                self.__merge_keyfiles(keyfile_password, remote_copy.name, local_copy.name)
                print("merging remote keyfile into local...")
                self.__merge_keyfiles(keyfile_password, local_copy.name, remote_copy.name)
                
                # overwrite remote and local with up to date file
                shutil.copy(remote_copy.name, self.__remote_keyfile_path)
                print("{} synchronized".format(self.__remote_keyfile_path))
                shutil.copy(local_copy.name, self.__local_keyfile_path)
                print("{} synchronized".format(self.__local_keyfile_path))

        return True, None

    def __ask_for_keyfile_password(self):
        return getpass.getpass(prompt = "Keyfile password?")

    def __merge_keyfiles(self, keyfile_password, into_keyfile, from_keyfile):
        command = [ self.__keepassxc_cli, "merge", "--quiet", "--same-credentials", into_keyfile, from_keyfile ]

        proc = subprocess.Popen(command, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True)
        outs, errs = proc.communicate(input = keyfile_password)
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
        self.__make_readonly(remote_keyfile_backup_path)
        self.__make_readonly(local_keyfile_backup_path)

        return True, None

    def __make_readonly(self, file_path):
        os.chmod(file_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

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
