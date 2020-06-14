import gi
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


# from https://stackoverflow.com/a/4028943
home_dir = Path.home()
# from https://stackoverflow.com/a/31867043
script_dir = Path(sys.path[0])

class PhanNas:
    nas_host = "nas"

    def __init__(self):
        self.mount_point_dir = PurePath(str(home_dir) + "/__NAS__")

    def check_online(self):
        if self.ping(self.nas_host):
            return True, None
        else:
            return False, "{} is not online".format(self.nas_host)

    def check_mount_dir(self):
        if os.path.isdir(self.mount_point_dir):
            return True, None
        else:
            return False, "mount dir does not exist"

    # from https://stackoverflow.com/a/32684938
    def ping(self, host):
        """
        Returns True if host (str) responds to a ping request.
        Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
        """

        # Option for the number of packets as a function of
        param = '-n' if platform.system().lower()=='windows' else '-c'

        # Building the command. Ex: "ping -c 1 google.com"
        command = ['ping', param, '1', host]

        # call local ping command, suppress stdout and stderr output as we only care about exit code
        return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


class MyWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="PhanNAS Desktop",
            default_width=200, resizable=False)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.box)

        self.label = Gtk.Label("...")
        self.box.pack_start(self.label, True, True, 0)

        self.connect("show", self.on_window_show)

        self.phanNAS = PhanNas()

    def on_window_show(self, widget):
        print("on_window_show")
        self.thread = threading.Thread(target=self.do_things)
        self.thread.daemon = True
        self.thread.start()

    def do_things(self):
        self.info_label("Calling test.sh")
        proc = subprocess.run(str(script_dir) + "/test.sh", 
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("exit code={}\nstdout={}\nstderr={}".format(proc.returncode, proc.stdout, proc.stderr))

        time.sleep(3)
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
        time.sleep(3)
        self.info_label("All NAS drives connected!")
        time.sleep(3)
        GLib.idle_add(Gtk.main_quit)

    def failure(self, msg):
        print(msg)
        self.info_label(msg)

    def info_label(self, text):
        GLib.idle_add(self.set_label_text, text)

    def set_label_text(self, text):
        self.label.set_text(text)
        # return false to not be called again
        return False

print(type(script_dir))


win = MyWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()

# called after GTK process has ended (ie. window closed and Gtk.main_quit is called)
print("foo")
