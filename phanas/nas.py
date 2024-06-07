import platform
import subprocess

from subprocess import DEVNULL


class Nas:
    def __init__(self):
        self._host = "192.168.1.5"
        self._drive_sys = "sys"
        self._drives = [
            "backup",
            "bds",
            "emilie",
            "enfants",
            "films",
            "jeux",
            "lesaint",
            "livres",
            "musique",
            "phan",
            "photos",
            "programs",
            self._drive_sys,
            "series",
            "videos",
            "vrac",
        ]

    def host(self):
        return self._host

    def drive_sys(self):
        return self._drive_sys

    def drives(self):
        return self._drives

    def check_online(self):
        if self.__ping(self._host):
            return True, None
        else:
            return False, "{} is not online".format(self._host)

    # from https://stackoverflow.com/a/32684938
    def __ping(self, host):
        """
        Returns True if host (str) responds to a ping request.
        Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
        """

        # Option for the number of packets as a function of
        param = "-n" if platform.system().lower() == "windows" else "-c"

        # Building the command. Ex: "ping -c 1 google.com"
        command = ["ping", param, "1", self._host]

        # call local ping command, suppress stdout and stderr output as we only care about exit code
        return subprocess.call(command, stdout=DEVNULL, stderr=DEVNULL) == 0
