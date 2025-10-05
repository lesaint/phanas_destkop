import gi
import logging
import threading

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from phanas.phanas_desktop import Output, PhanasDesktop, PROGRAM_NAME

class AskForPassword:
    """
    Implements the locking mechanism to show, from the worker thread, a dialog asking for a password and wait for the
    user to provide it or press cancel.

    Sources:
    * dialog code: https://python-gtk-3-tutorial.readthedocs.io/en/latest/dialogs.html#example
    * lock usage: https://stackoverflow.com/a/24796823
    """
    def __init__(self, parent_window, prompt: str):
        self._parent_window = parent_window
        self._prompt = prompt
        self._password: str | None = None
        self._lock = threading.Condition()

    def show_dialog(self):
        with self._lock:
            try:
                self._show_dialog()
            finally:
                self._lock.notify_all()

    def _show_dialog(self):
        dialog = PasswordDialog(parent=self._parent_window, prompt=self._prompt)
        response = dialog.run()

        print("password:", dialog.password_entry.get_text())
        if response == Gtk.ResponseType.OK:
            self._password = dialog.password_entry.get_text()
            print("The OK button was clicked")
        elif response == Gtk.ResponseType.CANCEL:
            print("The Cancel button was clicked")

        dialog.destroy()

    def wait_for_password(self) -> str | None:
        with self._lock:
            self._lock.wait()

        return self._password

class PasswordDialog(Gtk.Dialog):

    def __init__(self, parent, prompt: str):
        super().__init__(title="Provide a password", transient_for=parent, flags=0)

        self.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        self.set_modal(True)
        self.set_default_size(150, 100)
        self.set_default_response(Gtk.ResponseType.OK)

        label = Gtk.Label(label=prompt)
        box = self.get_content_area()
        box.add(label)
        self.password_entry = Gtk.Entry()
        self.password_entry.set_activates_default(True)
        box.add(self.password_entry)

        self.show_all()


class MyWindow(Gtk.Window, Output):
    __persistent_msg = []
    __phanasDesktop = None

    def __init__(self, phanasDesktop):
        self.__phanasDesktop = phanasDesktop

        Gtk.Window.__init__(
            self, title=PROGRAM_NAME, default_width=200, resizable=False
        )

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
        self.__phanasDesktop.do_things(input_provider=self, output=self)

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
            return "* " + "\n* ".join(self.__persistent_msg) + "\n" + msg
        return msg

    def set_label_text(self, text):
        self.label.set_text(text)
        # return false to not be called again
        return False

    def get_password(self, prompt: str) -> str | None:
        ask_for_password = AskForPassword(parent_window=self, prompt=prompt)
        GLib.idle_add(ask_for_password.show_dialog)

        return ask_for_password.wait_for_password()


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
