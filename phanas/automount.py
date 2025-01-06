import getpass
import logging
import os
import phanas.nas
import phanas.file_utils
import subprocess
import sys

from pathlib import Path
from subprocess import PIPE
from abc import abstractmethod, ABC

MOUNT_DIR_NAME = "__NAS__"
LOGGER_NAME = "automount"


class Env:
    linux_username = getpass.getuser()
    # from https://stackoverflow.com/a/4028943
    home_dir_path = Path.home()
    # base_mount_dir_path must not be location in /home or /media to not have drive loaded by Nautilus
    # and slow down Gnome's login
    # logical links in /home to mounted drive outside /home are not loaded by Nautilus
    base_mount_dir_path = Path("/mnt/" + MOUNT_DIR_NAME)
    mount_dir_path = base_mount_dir_path / linux_username
    # from https://stackoverflow.com/a/31867043
    __script_dir = Path(sys.path[0])
    deprecated_credential_file_path = Path(__script_dir) / ".phanas"
    credential_file_path = Path(__script_dir) / ".smb_phanas"


class AutoMountLogger(ABC):
    @abstractmethod
    def info(self, msg: str) -> None:
        """ Informative message typically describing an achieved state"""
        pass

    @abstractmethod
    def transient_info(self, msg: str) -> None:
        """ Informative message typically describing an ongoing operation rather than an achieved state"""
        pass

    @abstractmethod
    def error(self, msg: str) -> None:
        """ Error message"""
        pass


class DefaultAutMountLogger(AutoMountLogger):
    def __init__(self):
        self._logger = logging.getLogger(LOGGER_NAME)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def transient_info(self, msg: str) -> None:
        self._logger.debug(msg)

    def error(self, msg: str) -> None:
        self._logger.error(msg)


class AutoMount:
    def __init__(self):
        self._logger = logging.getLogger(LOGGER_NAME)
        self.env = Env()
        self.nas = phanas.nas.Nas()
        self._logger.info("Mount dir=%s", self.env.base_mount_dir_path)

    def run(self, automount_logger: AutoMountLogger = DefaultAutMountLogger()) -> bool:
        automount_logger.info("Automount started")

        if not self._check_linux():
            automount_logger.info(
                "Connecting NAS drives: no action, only supported on Linux"
            )
            return True

        automount_logger.transient_info("Checking NAS is online...")
        status, msg = self._check_online()
        if not status:
            automount_logger.error(msg)
            return False

        automount_logger.transient_info("Checking file prerequisites...")
        status, msg = self._check_file_prerequisites()
        if not status:
            automount_logger.error(msg)
            return False

        automount_logger.transient_info("Connecting NAS drives...")
        status, msg = self._connect_drives()
        if not status:
            automount_logger.error(msg)
            return False

        automount_logger.transient_info("Configuring desktop...")
        status, msg = self._configure_desktop()
        if not status:
            automount_logger.error(msg)
            return False

        automount_logger.info("All NAS drives connected!")
        return True

    @staticmethod
    def _check_linux():
        return sys.platform.startswith("linux")

    # def check_system_prerequisites(self):
    # check cifs-utils is installed
    # from https://askubuntu.com/a/336739
    # $ apt-cache policy cifs-utils

    def _check_online(self):
        status, msg = self.nas.check_online()
        if not status:
            return False, msg

        return True, None

    def _check_file_prerequisites(self):
        if not self.env.base_mount_dir_path.is_dir():
            return False, "mount dir does not exist"

        # TODO check permission will allow to create subdirectory per NAS user

        status, msg = self.__check_and_load_credentials_file()
        if not status:
            return False, msg

        return True, None

    def __check_and_load_credentials_file(self):
        status, msg = self.__migrate_from_deprecated_credentials_file()
        if not status:
            return False, msg

        status, msg, username, pwd = phanas.file_utils.read_credentials_file(
            self.env.credential_file_path
        )
        if not status:
            return False, msg
        self._logger.info("PhanNas username: %s", username)

        return True, None

    def __migrate_from_deprecated_credentials_file(self):
        if not self.env.deprecated_credential_file_path.is_file():
            return True, None

        if self.env.credential_file_path.is_file():
            return False, "Both deprecated and new credentials file are present"
        self._logger.info("derecated credentials file detected, renaming it...")
        os.rename(
            self.env.deprecated_credential_file_path, self.env.credential_file_path
        )

        mounted_drives = []
        for drive in self.nas.drives():
            device, sub_dir_path = self.__drive_and_dir_for(self.nas, drive, drive)
            if sub_dir_path.is_dir() and os.path.ismount(sub_dir_path):
                mounted_drives.append(drive)

        if mounted_drives:
            return False, "The following drives must be remounted: {}".format(
                ", ".join(mounted_drives)
            )

        return True, None

    def __connect_drives(self, nas, global_status, global_msg):
        for drive in nas.drives():
            status, msg = self.__connect_drive(nas, drive, drive)
            if not status:
                global_status = False
                global_msg.append(msg)

    def _connect_drives(self):
        if not self.env.mount_dir_path.exists():
            self._logger.info(
                "mount dir %s for user does not exist, creating it...",
                self.env.mount_dir_path,
            )
            self.env.mount_dir_path.mkdir()
        elif not self.env.mount_dir_path.is_dir():
            return False, "{} should be a directory".format(self.env.mount_dir_path)

        global_status = True
        global_msg = []
        self.__connect_drives(self.nas, global_status, global_msg)

        return global_status, "\n".join(global_msg)

    def __connect_drive(self, nas, nas_drive, mount_sub_dir):
        device, sub_dir_path = self.__drive_and_dir_for(nas, nas_drive, mount_sub_dir)
        self._logger.info("Mounting %s into %s... ", device, sub_dir_path)

        mounted, msg = self.__is_already_mounted(sub_dir_path, device)
        if mounted:
            self._logger.info("already mounted")
            return True, None
        status, msg = self.__check_mount_dir(sub_dir_path)
        if msg is not None:
            return False, msg

        if not status:
            return False, msg

        status, msg = self.__mount_drive(sub_dir_path, device)
        if status:
            self._logger.info("mounted")
        else:
            return False, msg

        return True, None

    def __drive_and_dir_for(self, nas, nas_drive, mount_sub_dir):
        device = "//{}/{}".format(nas.host(), nas_drive)
        sub_dir_path = self.env.mount_dir_path / mount_sub_dir

        return device, sub_dir_path

    def __check_mount_dir(self, sub_dir_path):
        if not sub_dir_path.exists():
            self._logger.info(
                "Mount sub dir %s does not exist. Creating it...", sub_dir_path
            )
            sub_dir_path.mkdir()
            return True, None
        if not sub_dir_path.is_dir():
            return False, "{} is not a directory".format(sub_dir_path)
        if not phanas.file_utils.is_empty_dir(sub_dir_path):
            return False, "{} is not empty".format(sub_dir_path)

        return True, None

    def __is_already_mounted(self, dir_path, expected_device):
        if not os.path.ismount(dir_path):
            return False, None

        command = [
            "/bin/findmnt",
            # exit with 1 if directory is not mounted
            "--target",
            dir_path,
            # do not output column headers
            "--noheadings",
            # output only the device
            "--output",
            "SOURCE",
        ]

        findmount_process = subprocess.run(
            command, stdout=PIPE, stderr=PIPE, encoding="utf-8"
        )
        if findmount_process.returncode == 1:
            return False, None

        actual_device = findmount_process.stdout
        if expected_device == actual_device.split("\n")[0]:
            return True, None
        else:
            return False, "{} mounted to the wrong device: {}".format(
                dir_path, actual_device
            )

    def __mount_drive(self, dir_path, device):
        # https://unix.stackexchange.com/a/104652 for file_mode and dir_mode => files can't be made executable on samdba drive (unless they all are executable)
        mount_options = (
            "uid={},gid={},vers=2.1,file_mode=0644,dir_mode=0755,credentials={}".format(
                os.getuid(), os.getgid(), self.env.credential_file_path
            )
        )
        command = [
            "sudo",
            # will fail if password needed => require sudoers to be configured in advance
            # --reset-timestamp ignores previously provided password
            "--non-interactive",
            "--reset-timestamp",
            "mount",
            "--types",
            "cifs",
            device,
            str(dir_path),
            "--options",
            mount_options,
        ]

        p = subprocess.run(
            command, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True
        )
        if p.returncode == 0:
            return True, None
        else:
            return False, "Failed to mount {} in {}: {}".format(
                device, dir_path, p.stderr
            )

    def _configure_desktop(self):
        status, msg = self.__configure_nas_directory()
        if not status:
            return False, msg

        # TODO: add/ensure bookmark to linux users' __NAS__ dir exists in Nautilus
        #       just add URL of directory to ~/.gtk-bookmarks

        return True, None

    def __configure_nas_directory(self):
        user_nas_dir_path = self.env.home_dir_path / MOUNT_DIR_NAME
        if not user_nas_dir_path.exists():
            self._logger.info("Creating user NAS directory %s...", user_nas_dir_path)
            user_nas_dir_path.mkdir()
        elif not user_nas_dir_path.is_dir():
            return False, "User NAS directory {} is not a directory".format(
                user_nas_dir_path
            )

        status, msg = self.___create_symlinks(user_nas_dir_path)
        if not status:
            return False, msg

        return True, None

    def ___create_symlinks(self, user_nas_dir_path):
        global_status = True
        global_msg = []
        for drive in self.nas.drives():
            status, msg = self.__create_symlink(user_nas_dir_path, drive)
            if not status:
                global_status = False
                global_msg.append(msg)

        if not global_status:
            return False, "\n".join(global_msg)

        return True, None

    def __create_symlink(self, user_nas_dir_path, drive):
        symlink_path = user_nas_dir_path / drive
        symlink_target = self.env.mount_dir_path / drive

        if not symlink_path.exists():
            self._logger.info("Creating symlink %s", symlink_path)
            symlink_path.symlink_to(symlink_target, target_is_directory=True)
        elif not symlink_path.is_symlink():
            return False, "{} is not a symlink".format(symlink_path)
        else:
            actual_target = symlink_path.resolve()
            if actual_target != symlink_target:
                return (
                    False,
                    "{} does not target expected directory (got={}, expected={})".format(
                        symlink_path, actual_target, symlink_target
                    ),
                )

        return True, None
