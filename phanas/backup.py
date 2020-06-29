import logging
import os
import select
import subprocess

from pathlib import Path
from io import StringIO

class Backup:
    __logger = logging.getLogger("backup")

    __script_path = None
    
    def __init__(self, config):
        self.__load_backupscript_path(config)

    def __load_backupscript_path(self, config):
        backup_name = "backup"
        script_path_name = "script_path"

        if not config:
            self.__logger.info("no config")
            return False

        if not backup_name in config:
            self.__logger.info("config does not contain %s", backup_name)
            return False

        backup_config = config[backup_name]
        if not isinstance(backup_config, dict) or not script_path_name in backup_config:
            self.__logger.info("'%s' is not an object or does not contain name '%s'", backup_name, script_path_name)
            return False

        script_path_str = backup_config[script_path_name]
        if not isinstance(script_path_str, str) or not script_path_str:
            self.__logger.info("%s is not a string", script_path_name)
            return False

        script_path = Path(script_path_str)
        if not script_path.is_file():
            self.__logger.error("script %s can not be found", script_path)
            return False

        if not os.access(script_path, os.X_OK):
            self.__logger.error("script %s is not executable", script_path)
            return False

        self.__logger.info("backup script: %s", script_path)
        self.__script_path = script_path

        return True

    def should_backup(self):
        if self.__script_path:
            return True

        return False

    def do_backup(self):
        command = [ self.__script_path ]

        proc = subprocess.Popen(command, stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE, universal_newlines = True)

        def check_std(std, loglevel):
           while True:
                output = std.readline()
                if output:
                    self.__logger.log(loglevel, output.strip())
                else:
                    break 

        def check_io():
            check_std(proc.stdout, logging.INFO)
            check_std(proc.stderr, logging.ERROR)

        while proc.poll() is None:
            check_io()
            proc.wait()

        if proc.returncode != 0:
            return False, "backup script had an error. Check the logs".format(proc.stderr)

        return True, None


def run(config):
    logger = logging.getLogger("backup")
    logger.info("Backup to Phanas started")

    backup = Backup(config)

    if backup.should_backup():
        status, msg = backup.do_backup()
        if not status:
            logger.error(msg)
    else:
        logger.info("Backup is not configured")

    logger.info("Backup to Phanas done")
