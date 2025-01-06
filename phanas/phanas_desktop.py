import logging
import phanas.automount as automount
import phanas.backup
import phanas.keepass
import phanas.nascopy
import time

from phanas.automount import AutoMountLogger

PROGRAM_NAME = "PhanNas Desktop"


class Output:
    def failure(self, msg):
        pass

    def add_persistent_msg(self, msg):
        pass

    def info_label(self, text):
        pass

    def close(self):
        pass


class PhanasDesktop:
    def __init__(self, config, logger: logging.Logger):
        self.__config = config
        self.__logger = logger

        self.autoMount = automount.AutoMount()

    def _do_automount(self, output: Output):
        class PersistentMsgAutoMountLogger(AutoMountLogger):
            def __init__(self, phanas_desktop: PhanasDesktop):
                self._phanas_desktop = phanas_desktop

            def info(self, msg: str) -> None:
                self._phanas_desktop.add_persistent_msg(output, msg)

            def transient_info(self, msg: str) -> None:
                self._phanas_desktop.info_label(output, msg)

            def error(self, msg: str) -> None:
                self._phanas_desktop.failure(output, msg)

        self.autoMount.run(PersistentMsgAutoMountLogger(self))

    def _do_keyfile_synchronization(self, output):
        self.info_label(output, "Synchronizing keyfiles...")
        keepass = phanas.keepass.KeePass(self.__config)
        if keepass.should_synch_keyfiles():
            status, msg = keepass.do_sync()
            if not status:
                self.failure(output, msg)
                return False
            self.add_persistent_msg(output, "Keyfiles synchronized")
        else:
            self.info_label(output, "Keyfile synchronization not configured")

        return True

    def _do_nascopy(self, output):
        self.info_label(output, "Synchronizing NAS copy... should be quick...")
        nascopy = phanas.nascopy.NasCopy(self.__config)
        if nascopy.should_nascopy():
            status, msg = nascopy.do_nascopy()
            if not status:
                self.failure(output, msg)
                return False
            self.add_persistent_msg(output, "NAS copy done")
        else:
            self.info_label(output, "NAS copy not configured")

        return True

    def _do_backup(self, output):
        self.info_label(output, "Creating backup... can take a while!")
        backup = phanas.backup.Backup(self.__config)
        if backup.should_backup():
            if backup.can_skip():
                self.add_persistent_msg(output, "Backup done (skipped, recent enough)")
            else:
                status, msg = backup.do_backup()
                if not status:
                    self.failure(output, msg)
                    return
                self.add_persistent_msg(output, "Backup done")
        else:
            self.info_label(output, "Backup not configured")

    def _do_things(self, output: Output):
        if not self._do_automount(output):
            return
        if not self._do_keyfile_synchronization(output):
            return
        if not self._do_nascopy(output):
            return
        self._do_backup(output)

    def do_things(self, output: Output):
        self._do_things(output)

        self.info_label(output, "     Closing in 3 seconds...")
        time.sleep(3)
        self._close(output)

    def failure(self, output, msg):
        self.__logger.error(msg)
        output.failure(msg)

    def info_label(self, output, text):
        self.__logger.info(text)
        output.info_label(text)

    def add_persistent_msg(self, output, msg):
        self.__logger.info(msg)
        output.add_persistent_msg(msg)

    def _close(self, output):
        self.__logger.info("closing...")
        output.close()
