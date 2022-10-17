import gi
import logging
import threading

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from phanas.phanas_desktop import Output, PhanasDesktop

PROGRAM_NAME = "PhanNas Desktop"

class MyWindow(Gtk.Window, Output):
    __persistent_msg = []
    __phanasDesktop = None

    def __init__(self, phanasDesktop):
        self.__phanasDesktop = phanasDesktop

        Gtk.Window.__init__(self, title=PROGRAM_NAME,
            default_width=200, resizable=False)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.box)

        self.label = Gtk.Label("...")
        self.box.pack_start(self.label, True, True, 0)

        self.connect("destroy", Gtk.main_quit)
        self.connect("show", self.on_window_show)

    def show(self):
        self.show_all()
        Gtk.main()

    def on_window_show(self, widget):
        self.thread = threading.Thread(target=self._do_things)
        self.thread.daemon = True
        self.thread.start()

    def _do_things(self):
        self.__phanasDesktop.do_things(self)

    def failure(self, msg):
        self.info_label(msg)

    def add_persistent_msg(self, msg):
        effective_msg = self.__effective_msg_of(msg)
        self.__persistent_msg.append(msg)
        GLib.idle_add(self.set_label_text, effective_msg)

    def info_label(self, text):
        effective_text = self.__effective_msg_of(text)
        GLib.idle_add(self.set_label_text, effective_text)

    def __effective_msg_of(self, msg):
        if self.__persistent_msg:
            return "* "  + "\n* ".join(self.__persistent_msg) + "\n" + msg
        return msg

    def set_label_text(self, text):
        self.label.set_text(text)
        # return false to not be called again
        return False

    def close(self):
        GLib.idle_add(Gtk.main_quit)

def run(config):
    logger = logging.getLogger("login_gui")
    logger.info("%s started", PROGRAM_NAME)

    phanasDesktop = PhanasDesktop(config, logger)
    win = MyWindow(phanasDesktop)
    win.show()

    # called after GTK process has ended (ie. window closed and/or Gtk.main_quit is called)
    logger.info("%s stopped", PROGRAM_NAME)
