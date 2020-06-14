#!/usr/bin/env python3

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

    def __init__(self):
        self.mount_dir_path = Path(str(home_dir) + "/" + MOUNT_DIR_NAME)
        print("Mount dir={}".format(self.mount_dir_path))

    #def check_system_prerequisites(self):
        # check cifs-utils is installed
        # from https://askubuntu.com/a/336739
        # $ apt-cache policy cifs-utils
        #
        # TODO check credentials file is present and has correct permissions (600)

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

    def check_mount_dir(self):
        if self.mount_dir_path.is_dir():
            return True, None
        else:
            return False, "mount dir does not exist"

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
        mount_options = "uid=1001,vers=2.1,credentials={}/.phanas".format(script_dir)
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

    def generate_sudoers(self, user):
        mnt_aliases = list(map(lambda x: "/bin/mount --types cifs //{}/{} {}/{} *".format(self.nas_host, x, self.mount_dir_path, x), NAS_DRIVES))
        umnt_aliases = list(map(lambda x: "/bin/umount {}/{}".format(self.mount_dir_path, x), NAS_DRIVES))

        txt = """
Cmnd_Alias MOUNT_NAS = \\
{}
Cmnd_Alias UMOUNT_NAS = \\
{}

# Allow user {} to mount and umount NAS drives without password
{} ALL=(ALL) NOPASSWD: MOUNT_NAS, UMOUNT_NAS
""".format(", \\\n".join(mnt_aliases), ", \\\n".join(umnt_aliases), user, user)
        
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
        print(self.phanNAS.generate_sudoers(getpass.getuser()))

        self.info_label("Checking NAS is online...")
        status, msg = self.phanNAS.check_online()
        if not status:
            self.failure(msg)
            return
        self.info_label("Checking mount dir...")
        status, msg = self.phanNAS.check_mount_dir()
        if not status:
            self.failure(msg)
            return
        self.info_label("Connecting NAS drives...")
        status, msg = self.phanNAS.connect_drives()
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

print("{} started".format(PROGRAM_NAME))

win = MyWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()

# called after GTK process has ended (ie. window closed and/or Gtk.main_quit is called)
print("{} stopped".format(PROGRAM_NAME))
