import gi
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


class MyWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Hello World")

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.box)

        self.button1 = Gtk.Button(label="Hello")
        self.button1.connect("clicked", self.on_button1_clicked)
        self.box.pack_start(self.button1, True, True, 0)

        self.label = Gtk.Label("Goodbye")
        self.box.pack_start(self.label, True, True, 0)

        self.connect("show", self.on_window_show)

    def on_button1_clicked(self, widget):
        print("Hello")
        self.info_label("Foo Bar 2000 blablablablabla!")

    def on_window_show(self, widget):
        print("on_window_show")
        GLib.timeout_add_seconds(1, self.check_nas_online)

    def info_label(self, text):
        self.label.set_text(text)

    def check_nas_online(self):
        self.info_label("Checking NAS is online...")
        GLib.timeout_add_seconds(3, self.connect_nas_drives)

        # return false to not be called again
        return False

    def connect_nas_drives(self):
        self.info_label("Connecting NAS drives...")
        GLib.timeout_add_seconds(3, self.connect_done_ok)

        # return false to not be called again
        return False

    def connect_done_ok(self):
        self.info_label("All NAS drives connected!")

        # return false to not be called again
        return False


win = MyWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()

# called after GTK process has ended (ie. window closed and Gtk.main_quit is called)
print("foo")
