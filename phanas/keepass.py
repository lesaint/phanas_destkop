
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
    __KEEPASSXC_CLI = "keepassxc-cli"
    __keepassxc_cli = None

    __MD5SUM = "md5sum"
    __md5sum = None

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
    __sync_backup_dir_path = None

    __KEYFILE_NAME = "sebastienlesaint.kdbx"
    __remote_keyfile_path = None
    __local_keyfile_path = Path.home() / __KEYFILE_NAME

    def should_synch_keyfiles(self):
        return self.__local_keyfile_path.is_file()

    def do_sync(self):
        status, msg = self._check_prerequisites()
        if not status:
            return False, msg

        status, msg = self._synch_files()
        if not status:
            return False, msg

        return True, None

    def _check_prerequisites(self):
        # keepassxc-cli is installed
        self.__keepassxc_cli = shutil.which(self.__KEEPASSXC_CLI)
        if self.__keepassxc_cli is None:
            return False, "{} is not installed".format(self.__KEEPASSXC_CLI)
        print("keepassxc-cli found: {}".format(self.__keepassxc_cli))

        self.__md5sum = shutil.which(self.__MD5SUM)
        if self.__md5sum is None:
            return False, "{} is not installed".format(self.__MD5SUM)

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
        self.__sync_backup_dir_path = self.__remote_keyfile_dir_path / "{backup_dir}/{host}/{linux_user}".format(
            backup_dir = "_sync_backup", host = self.__hostname, linux_user = self.__linux_username)

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

    def _synch_files(self):
        status, msg = self.__need_sync()
        if not status:
            if msg:
                return False, msg
            print("Keyfiles have not changed")
            return True, None

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

    def __need_sync(self):
        latest_local_backup_path, local_timestamp = self.__get_latest_backup(True)
        latest_remote_backup_path, remote_timestamp = self.__get_latest_backup(False)

        if latest_local_backup_path is None or latest_remote_backup_path is None:
            return True, None

        if not local_timestamp == remote_timestamp:
            return False, "Latest backup of remote ({}) doesn't have the same timestamp as latest backup of local ({})".format(
                latest_remote_backup_path.name, latest_local_backup_path.name)

        local_keyfile_unchanged = phanas.file_utils.has_same_content(latest_local_backup_path, self.__local_keyfile_path)
        remote_keyfile_unchanged = phanas.file_utils.has_same_content(latest_remote_backup_path, self.__remote_keyfile_path)
        if local_keyfile_unchanged and remote_keyfile_unchanged:
            return False, None

        return True, None

    def __get_latest_backup(self, local):
        if not self.__sync_backup_dir_path.is_dir():
            return None, None

        glob = "*_{nas_or_local}_{keyfilename}".format(nas_or_local = "local" if local else "nas", keyfilename = self.__KEYFILE_NAME)
        max_date = None
        latest_backup_path = None
        for file in self.__sync_backup_dir_path.glob(glob):
            timestamp = self.__read_timestamp_from_backup_file(file)
            if max_date is None or max_date < timestamp:
                max_date = timestamp
                latest_backup_path = file

        return latest_backup_path, max_date

    def __merge_keyfiles(self, into_keyfile, from_keyfile):
        command = [ self.__keepassxc_cli, "merge", "--quiet", "--same-credentials", into_keyfile, from_keyfile ]

        proc = subprocess.Popen(command, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True)
        outs, errs = proc.communicate(input = self.__keyfile_password)
        print("output=" + outs)
        print("errs=" + errs)

    def __backup_keyfiles(self):
        status, msg = self.__expire_old_backups()
        if not status:
            return False, msg

        # sync backup directory exists or we create it
        for d in [self.__sync_backup_dir_path.parents[1], self.__sync_backup_dir_path.parents[0], self.__sync_backup_dir_path]:
            if not d.exists():
                print("{} does not exists, creating it...".format(d))
                d.mkdir()
            elif not d.is_dir():
                return False, "{} is not a directory".format(d)

        timestamp = datetime.today().strftime(self.__BACKUP_TIMESTAMP_FORMAT)
        remote_keyfile_backup_path = self.__sync_backup_dir_path / "{date}_nas_{keyfilename}".format(date = timestamp, keyfilename = self.__KEYFILE_NAME)
        local_keyfile_backup_path = self.__sync_backup_dir_path / "{date}_local_{keyfilename}".format(date = timestamp, keyfilename = self.__KEYFILE_NAME)
        if remote_keyfile_backup_path.exists() or local_keyfile_backup_path.exists():
            return False, "backup file {} or {} already exists".format(remote_keyfile_backup_path, local_keyfile_backup_path)

        shutil.copyfile(self.__remote_keyfile_path, remote_keyfile_backup_path, follow_symlinks = False)
        shutil.copyfile(self.__local_keyfile_path, local_keyfile_backup_path, follow_symlinks = False)
        phanas.file_utils.make_readonly(remote_keyfile_backup_path)
        phanas.file_utils.make_readonly(local_keyfile_backup_path)

        return True, None

    def __expire_old_backups(self):
        if not self.__sync_backup_dir_path.is_dir():
            return True, None

        for file in self.__sync_backup_dir_path.glob("*.kdbx"):
            day = self.__read_day_from_backup_file(file)
            threshold_day = datetime.today() - timedelta(days = self.__BACKUP_EXPIRATION_IN_DAYS)
            if day < threshold_day:
                print("deleting old backup {}...".format(file))
                file.unlink()

        return True, None

    def __read_day_from_backup_file(self, file_path):
        day_str = file_path.stem[0:len("2020-06-18")]
        return datetime.strptime(day_str, self.__BACKUP_DATE_FORMAT)

    def __read_timestamp_from_backup_file(self, file_path):
        timestamp_str = file_path.stem[0:len("2020-06-18_09-32-45")]
        return datetime.strptime(timestamp_str, self.__BACKUP_TIMESTAMP_FORMAT)

def run():
    print("Keepass synchronization started\n")

    keepass = KeePass()
    status, msg = keepass.do_sync()
    if not status:
        print("[ERROR] {}".format(msg))

    # called after GTK process has ended (ie. window closed and/or Gtk.main_quit is called)
    print("\nKeepass synchronization done")
