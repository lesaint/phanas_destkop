import gi
import logging
import phanas.automount as automount
import phanas.backup
import phanas.keepass
import phanas.nascopy
import threading
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

PROGRAM_NAME = "PhanNas Desktop"

class Output:
    def initialize(self, runEngine):
        pass

    def failure(self, msg):
        pass

    def add_persistent_msg(self, msg):
        pass

    def info_label(self, text):
        pass

    def close(self):
        pass

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

class PhanasDesktop:
    __config = None
    __logger = None
    __output = None

    def __init__(self, config, logger):
        self.__config = config
        self.__logger = logger

        self.autoMount = automount.AutoMount()

    def do_things(self, output):
        self._info_label(output, "Checking NAS is online...")
        status, msg = self.autoMount.check_online()
        if not status:
            self._failure(msg)
            return
        
        self._info_label(output, "Checking file prerequisites...")
        status, msg = self.autoMount.check_file_prerequisites()
        if not status:
            self._failure(output, msg)
            return

        self._info_label(output, "Connecting NAS drives...")
        status, msg = self.autoMount.connect_drives()
        if not status:
            self._failure(output, msg)
            return

        self._info_label(output, "Configuring desktop...")
        status, msg = self.autoMount.configure_desktop()
        if not status:
            self._failure(output, msg)
            return

        self._add_persistent_msg(output, "All NAS drives connected!")

        self._info_label(output, "Synchronizing keyfiles...")
        keepass = phanas.keepass.KeePass(self.__config)
        if keepass.should_synch_keyfiles():
            status, msg = keepass.do_sync()
            if not status:
                self._failure(output, msg)
                return
            self._add_persistent_msg(output, "Keyfiles synchronized")
        else:
            self._info_label(output, "Keyfile synchronization not configured")

        self._info_label(output, "Synchronizing NAS copy... should be quick...")
        nascopy = phanas.nascopy.NasCopy(self.__config)
        if nascopy.should_nascopy():
            status, msg = nascopy.do_nascopy()
            if not status:
                self._failure(output, msg)
                return
            self._add_persistent_msg(output, "NAS copy done")
        else:
            self._info_label(output, "NAS copy not configured")


        self._info_label(output, "Creating backup... can take a while!")
        backup = phanas.backup.Backup(self.__config)
        if backup.should_backup():
            if backup.can_skip():
                self._add_persistent_msg(output, "Backup done (skipped, recent enough)")
            else:
                status, msg = backup.do_backup()
                if not status:
                    self._failure(output, msg)
                    return
                self._add_persistent_msg(output, "Backup done")
        else:
            self._info_label(output, "Backup not configured")
        
        self._info_label(output, "     Closing in 3 seconds...")
        time.sleep(3)
        self._close(output)

    def _failure(self, output):
        self.__logger.error(msg)
        output.failure(msg)

    def _info_label(self, output, text):
        self.__logger.info(text)
        output.info_label(text)

    def _add_persistent_msg(self, output, msg):
        self.__logger.info(msg)
        output.add_persistent_msg(msg)

    def _close(self, output):
        self.__logger.info("closing...")
        output.close()

def run(config):
    logger = logging.getLogger("login_gui")
    logger.info("%s started", PROGRAM_NAME)

    phanasDesktop = PhanasDesktop(config, logger)
    win = MyWindow(phanasDesktop)
    win.show()

    # called after GTK process has ended (ie. window closed and/or Gtk.main_quit is called)
    logger.info("%s stopped", PROGRAM_NAME)
