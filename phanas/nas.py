
import platform
import subprocess

from subprocess import DEVNULL

class Nas:
    host = "nas"
    drive_sys = "sys"
    drives = [
        "backup", "bds", "emilie", "enfants", "films", "jeux",
        "musique", "phan", "photos", "programs", "series", drive_sys, "videos", "vrac", "lesaint"
        # deprecated?
        #, "dev"
    ]

    def check_online(self):
        if self.__ping(self.host):
            return True, None
        else:
            return False, "{} is not online".format(self.host)

	# from https://stackoverflow.com/a/32684938
    def __ping(self, host):
        """
        Returns True if host (str) responds to a ping request.
        Remember that a host may not respond to a ping (ICMP) request even if the host name is valid.
        """

        # Option for the number of packets as a function of
        param = "-n" if platform.system().lower()=="windows" else "-c"

        # Building the command. Ex: "ping -c 1 google.com"
        command = ["ping", param, "1", host]

        # call local ping command, suppress stdout and stderr output as we only care about exit code
        return subprocess.call(command, stdout=DEVNULL, stderr=DEVNULL) == 0