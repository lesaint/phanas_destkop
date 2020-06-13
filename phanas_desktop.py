import gi
import subprocess
import threading
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


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
        time.sleep(3)
        self.info_label("Checking NAS is online...")
        time.sleep(3)
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


win = MyWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()

# called after GTK process has ended (ie. window closed and Gtk.main_quit is called)
print("foo")
