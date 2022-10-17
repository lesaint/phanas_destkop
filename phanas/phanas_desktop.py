import logging
import phanas.automount as automount
import phanas.backup
import phanas.keepass
import phanas.nascopy
import time

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

    def _failure(self, output, msg):
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
