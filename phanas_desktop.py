#!/usr/bin/env python3

import argparse
import gi
import getpass
import io
import os
import pathlib
import platform
import subprocess
import sys
import threading
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from pathlib import Path, PurePath
from subprocess import PIPE, DEVNULL

PROGRAM_NAME = "PhanNas Desktop"
MOUNT_DIR_NAME = "__NAS__"
NAS_DRIVES = [
    "backup", "bds", "dev", "emilie", "enfants", "films", "jeux",
    "musique", "phan", "photos", "programs", "series", "sys", "videos", "vrac"
    # deprecated?
    , "lesaint"
    # hidden
    , "xxx"
]

# from https://stackoverflow.com/a/4028943
home_dir = Path.home()
# from https://stackoverflow.com/a/31867043
script_dir = Path(sys.path[0])

class PhanNas:
    nas_host = "nas"
    nas_username = None
    base_mount_dir_path = None
    mount_dir_path = None
    credential_file_path = None
    linux_username = None

    def __init__(self):
        # base_mount_dir_path must not be location in /home or /media to not have drive loaded by Nautilus
        # and slow down Gnome's login
        # logical links in /home to mounted drive outside /home are not loaded by Nautilus
        self.base_mount_dir_path = Path("/" + MOUNT_DIR_NAME)
        self.credential_file_path = Path(script_dir) / ".phanas"
        self.linux_username = getpass.getuser()
        print("Mount dir={}".format(self.base_mount_dir_path))

    # def check_system_prerequisites(self):
        # check cifs-utils is installed
        # from https://askubuntu.com/a/336739
        # $ apt-cache policy cifs-utils

    def check_online(self):
        if self._ping(self.nas_host):
            return True, None
        else:
            return False, "{} is not online".format(self.nas_host)

    # from https://stackoverflow.com/a/32684938
    def _ping(self, host):
        """
        Returns True if host (str) responds to a ping request.
        Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
        """

        # Option for the number of packets as a function of
        param = "-n" if platform.system().lower()=="windows" else "-c"

        # Building the command. Ex: "ping -c 1 google.com"
        command = ["ping", param, "1", host]

        # call local ping command, suppress stdout and stderr output as we only care about exit code
        return subprocess.call(command, stdout=DEVNULL, stderr=DEVNULL) == 0

    def check_file_prerequisites(self):
        if not self.base_mount_dir_path.is_dir():
            return False, "mount dir does not exist"

        # TODO check permission will allow to create subdirectory per NAS user

        status, msg = self._check_and_load_credentials_file()
        if not status:
            return False, msg

        return True, None

    def _check_and_load_credentials_file(self):
        # already called
        if self.nas_username:
            return True, None

        if not self.credential_file_path.is_file():
            return False, "crediential file is missing"

        stats = self.credential_file_path.stat()
        # see https://stackoverflow.com/a/5337329
        if oct(stats.st_mode)[-3:] != "600":
            return False, "Permission of {} must be 600".format(self.credential_file_path)

        with open(self.credential_file_path, 'r') as f:
            user_line_prefix = "username="
            pwd_line_prefix = "password="

            user_line = f.readline()
            if not user_line.startswith(user_line_prefix):
                return False, "Wrong first line in credentials file"
            # substring without prefix nor ending line return
            nas_username = user_line[len(user_line_prefix):-1]
            print("PhanNas username from credentials file={}".format(nas_username))
            if not nas_username:
                return False, "Missing username in credentials file"

            pwd_line = f.readline()
            if not pwd_line.startswith(pwd_line_prefix):
                return False, "Wrong second line in credentials file"
            nas_pwd = pwd_line[len(pwd_line_prefix):-1]
            if not nas_pwd:
                return False, "Missing password in credentials file"

        mount_dir_path = self.base_mount_dir_path / nas_username
        if not mount_dir_path.exists():
            print("mount dir {} for NAS username does not exist, creating it...".format(mount_dir_path))
            mount_dir_path.mkdir()
        elif not mount_dir_path.is_dir():
            return False, "{} should be a directory".format(mount_dir_path)

        self.nas_username = nas_username
        self.mount_dir_path = mount_dir_path

        return True, None

    def connect_drives(self):
        global_status = True
        global_msg = []
        for drive in NAS_DRIVES:
            status, msg = self._connect_drive(drive, drive)
            if not status:
                global_status = False
                global_msg.append(msg)

        return global_status, "\n".join(global_msg)

    def _connect_drive(self, nas_drive, mount_sub_dir):
        device = "//{}/{}".format(self.nas_host, nas_drive)
        sub_dir_path = self.mount_dir_path / mount_sub_dir

        print("Mounting {} into {}... ".format(device, sub_dir_path))

        mounted, msg = self._is_already_mounted(sub_dir_path, device)
        if mounted:
            print("already mounted")
            return True, None
        if msg is not None:
            return False, msg

        status, msg = self._check_mount_dir(sub_dir_path)
        if not status:
            return False, msg

        status, msg = self._mount_drive(sub_dir_path, device)
        if status:
            print("mounted")
        else:
            return False, msg

        return True, None

    def _check_mount_dir(self, sub_dir_path):
        if not sub_dir_path.exists():
            print("Mount sub dir {} does not exist. Creating it...".format(sub_dir_path))
            sub_dir_path.mkdir()
            return True, None
        if not sub_dir_path.is_dir():
            return False, "{} is not a directory".format(sub_dir_path)
        if not self._is_empty_dir(sub_dir_path):
            return False, "{} is not empty".format(sub_dir_path)

        return True, None

    def _is_empty_dir(self, dir_path):
        try:
            next(dir_path.iterdir())
            return False
        except StopIteration as e:
            return True

    def _is_already_mounted(self, dir_path, expected_device):
        if not os.path.ismount(str(dir_path)):
            return False, None

        command = [ "/bin/findmnt",
            # exit with 1 if directory is not mounted
            "--target", dir_path,
            # do not output column headers
            "--noheadings",
            # output only the device
            "--output", "SOURCE" ]

        findmount_process = subprocess.run(command,
            stdout=PIPE, stderr=PIPE, encoding="utf-8")
        if findmount_process.returncode == 1:
            return False, None

        actual_device = findmount_process.stdout
        if expected_device == actual_device.split("\n")[0]:
            return True, None
        else:
            return False, "{} mounted to the wrong device: {}".format(dir_path, actual_device)

    def _mount_drive(self, dir_path, device):
        mount_options = "uid=1001,vers=2.1,credentials={}".format(self.credential_file_path)
        command = [
            "sudo",
            # will fail if password needed => require sudoers to be configured in advance
            # --reset-timestamp ignores previously provided password
            "--non-interactive", "--reset-timestamp",
            "mount", "--types", "cifs", device, str(dir_path),
            "--options", mount_options
        ]

        p = subprocess.run(command, stdin=PIPE,
            stdout=PIPE, stderr=PIPE, universal_newlines=True)
        if p.returncode == 0:
            return True, None
        else:
            return False, "Failed to mount {} in {}: {}".format(device, dir_path, p.stderr)

    def configure_desktop(self):
        # TODO: create or verify __NAS__ dir in home directory with symlinks to each
        #       drive mounted
        #       that __NAS__ dir must not have any write permission to avoid user messing around with it
        #       (but we will give ourselves these permissions to be able to add/remove symlinks)
        status, msg = self._configure_nas_directory()
        if not status:
            return False, msg

        # TODO: add/ensure bookmark to linux users' __NAS__ dir exists in Nautilus
        #       just add URL of directory to ~/.gtk-bookmarks

        return True, None

    def _configure_nas_directory(self):
        user_nas_dir_path = Path.home() / MOUNT_DIR_NAME
        if not user_nas_dir_path.exists():
            print("Creating user NAS directory {}...".format(user_nas_dir_path))
            user_nas_dir_path.mkdir()
        elif not user_nas_dir_path.is_dir():
            return False, "User NAS directory {} is not a directory".format(user_nas_dir_path)

        status, msg = self._create_symlinks(user_nas_dir_path)
        if not status:
            return False, msg

        return True, None
        
    def _create_symlinks(self, user_nas_dir_path):
        global_status = True
        global_msg = []
        for drive in NAS_DRIVES:
            status, msg = self._create_symlink(user_nas_dir_path, drive)
            if not status:
                global_status = False
                global_msg.append(msg)

        if not global_status:
            return False, "\n".join(global_msg)

        return True, None

    def _create_symlink(self, user_nas_dir_path, drive):
        symlink_path = user_nas_dir_path / drive
        symlink_target = self.mount_dir_path / drive

        if not symlink_path.exists():
            print("Creating symlink {}".format(symlink_path))
            symlink_path.symlink_to(symlink_target, target_is_directory=True)
        elif not symlink_path.is_symlink():
            return False, "{} is not a symlink".format(symlink_path)
        else:
            actual_target = symlink_path.resolve()
            if actual_target != symlink_target:
                return False, "{} does not target expected directory (got={}, expected={})".format(symlink_path, actual_target, symlink_target)

        return True, None


    def generate_sudoers(self):
        self._check_and_load_credentials_file()

        mnt_aliases = list(map(lambda x: "/bin/mount --types cifs //{}/{} {}/{} *".format(self.nas_host, x, self.mount_dir_path, x), NAS_DRIVES))
        umnt_aliases = list(map(lambda x: "/bin/umount {}/{}".format(self.mount_dir_path, x), NAS_DRIVES))

        txt = """
Cmnd_Alias MOUNT_NAS = \\
{}
Cmnd_Alias UMOUNT_NAS = \\
{}

# Allow user {} to mount and umount NAS drives without password
{} ALL=(ALL) NOPASSWD: MOUNT_NAS, UMOUNT_NAS
""".format(", \\\n".join(mnt_aliases), ", \\\n".join(umnt_aliases), self.linux_username, self.linux_username)
        
        return txt


class MyWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title=PROGRAM_NAME,
            default_width=200, resizable=False)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.box)

        self.label = Gtk.Label("...")
        self.box.pack_start(self.label, True, True, 0)

        self.connect("show", self.on_window_show)

        self.phanNAS = PhanNas()

    def on_window_show(self, widget):
        self.thread = threading.Thread(target=self.do_things)
        self.thread.daemon = True
        self.thread.start()

    def do_things(self):
        self.info_label("Checking NAS is online...")
        status, msg = self.phanNAS.check_online()
        if not status:
            self.failure(msg)
            return
        
        self.info_label("Checking file prerequisites...")
        status, msg = self.phanNAS.check_file_prerequisites()
        if not status:
            self.failure(msg)
            return

        self.info_label("Connecting NAS drives...")
        status, msg = self.phanNAS.connect_drives()
        if not status:
            self.failure(msg)
            return

        self.info_label("Configuring {} desktop...")
        status, msg = self.phanNAS.configure_desktop()
        if not status:
            self.failure(msg)
            return        
        
        self.info_label("All NAS drives connected!\nClosing in 3 seconds...")
        time.sleep(3)
        GLib.idle_add(Gtk.main_quit)

    def failure(self, msg):
        print("[ERROR]  " + msg)
        self.info_label(msg)

    def info_label(self, text):
        GLib.idle_add(self.set_label_text, text)

    def set_label_text(self, text):
        self.label.set_text(text)
        # return false to not be called again
        return False

def desktop():
    print("{} started".format(PROGRAM_NAME))

    win = MyWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

    # called after GTK process has ended (ie. window closed and/or Gtk.main_quit is called)
    print("{} stopped".format(PROGRAM_NAME))

def generate_sudoers():
    phanNAS = PhanNas()
    status, msg = phanNAS.check_file_prerequisites()
    if not status:
        print("[ERROR]  " + msg)
        return
    print(phanNAS.generate_sudoers())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--generate-sudoers", help="generate sudoers commands for current linux and nas user", action="store_true")
    args = parser.parse_args()
    if args.generate_sudoers:
       generate_sudoers()
    else:
        desktop() 

if __name__ == '__main__':
   main()
