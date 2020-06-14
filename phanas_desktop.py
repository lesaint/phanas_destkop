import gi
import subprocess
import platform
import sys
import threading
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


script_dir = sys.path[0]

class MyWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="PhanNAS Desktop",
            default_width=200, resizable=False)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.box)

        self.label = Gtk.Label("...")
        self.box.pack_start(self.label, True, True, 0)

        self.connect("show", self.on_window_show)

    def on_window_show(self, widget):
        print("on_window_show")
        self.thread = threading.Thread(target=self.do_things)
        self.thread.daemon = True
        self.thread.start()

    def do_things(self):
        self.info_label("Calling test.sh")
        proc = subprocess.run(script_dir + "/test.sh", 
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("exit code={}\nstdout={}\nstderr={}".format(proc.returncode, proc.stdout, proc.stderr))

        time.sleep(3)
        self.info_label("Checking NAS is online...")
        hosts = ["nas", "NAS", "foo", "192.168.1.4", "192.168.1.98"]
        for host in hosts:
            if self.ping(host):
                print("{} is online".format(host))
            else:
                print("{} is not online".format(host))

        self.info_label("Connecting NAS drives...")
        time.sleep(3)
        self.info_label("All NAS drives connected!")
        time.sleep(3)
        GLib.idle_add(Gtk.main_quit)

    def info_label(self, text):
        GLib.idle_add(self.set_label_text, text)

    def set_label_text(self, text):
        self.label.set_text(text)
        # return false to not be called again
        return False

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

print(type(script_dir))


win = MyWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()

# called after GTK process has ended (ie. window closed and Gtk.main_quit is called)
print("foo")
