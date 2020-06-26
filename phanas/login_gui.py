import gi
import logging
import phanas.automount as automount
import phanas.keepass
import threading
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

PROGRAM_NAME = "PhanNas Desktop"

class MyWindow(Gtk.Window):
    __persistent_msg = []
    __config = None
    __logger = None

    def __init__(self, config, logger):

        Gtk.Window.__init__(self, title=PROGRAM_NAME,
            default_width=200, resizable=False)

        self.__config = config
        self.__logger = logger

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(self.box)

        self.label = Gtk.Label("...")
        self.box.pack_start(self.label, True, True, 0)

        self.connect("show", self.on_window_show)

        self.autoMount = automount.AutoMount()

    def on_window_show(self, widget):
        self.thread = threading.Thread(target=self.do_things)
        self.thread.daemon = True
        self.thread.start()

    def do_things(self):
        self.info_label("Checking NAS is online...")
        status, msg = self.autoMount.check_online()
        if not status:
            self.failure(msg)
            return
        
        self.info_label("Checking file prerequisites...")
        status, msg = self.autoMount.check_file_prerequisites()
        if not status:
            self.failure(msg)
            return

        self.info_label("Connecting NAS drives...")
        status, msg = self.autoMount.connect_drives()
        if not status:
            self.failure(msg)
            return

        self.info_label("Configuring desktop...")
        status, msg = self.autoMount.configure_desktop()
        if not status:
            self.failure(msg)
            return

        self.add_persistent_msg("All NAS drives connected!")

        self.info_label("Synchronizing keyfiles...")
        keepass = phanas.keepass.KeePass(self.__config)
        if keepass.should_synch_keyfiles():
            status, msg = keepass.do_sync()
            if not status:
                self.failure(msg)
                return
            self.add_persistent_msg("Keyfiles synchronized")
        else:
            self.info_label("Keyfile synchronization not configured")
        
        self.info_label("     Closing in 3 seconds...")
        time.sleep(3)
        GLib.idle_add(Gtk.main_quit)

    def failure(self, msg):
        self.__logger.error(msg)
        self.info_label(msg)

    def add_persistent_msg(self, msg):
        self.__logger.info(msg)
        effective_msg = self.__effective_msg_of(msg)
        self.__persistent_msg.append(msg)
        GLib.idle_add(self.set_label_text, effective_msg)

    def info_label(self, text):
        self.__logger.info(text)
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

def run(config):
    logger = logging.getLogger("login_gui")
    logger.info("%s started", PROGRAM_NAME)

    win = MyWindow(config, logger)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

    # called after GTK process has ended (ie. window closed and/or Gtk.main_quit is called)
    logger.info("%s stopped", PROGRAM_NAME)