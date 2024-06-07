import logging
import os
import subprocess
import sys

from pathlib import Path


class NasCopy:
    __logger = logging.getLogger("nascopy")

    __script_path = None

    def __init__(self, config):
        self.__load_nascopyscript_path(config)

    def __load_nascopyscript_path(self, config):
        nascopy_name = "nascopy"
        script_path_name = "script_path"

        if not config:
            self.__logger.info("no config")
            return False

        if not nascopy_name in config:
            self.__logger.info("config does not contain %s", nascopy_name)
            return False

        nascopy_config = config[nascopy_name]
        if (
            not isinstance(nascopy_config, dict)
            or not script_path_name in nascopy_config
        ):
            self.__logger.info(
                "'%s' is not an object or does not contain name '%s'",
                nascopy_name,
                script_path_name,
            )
            return False

        script_path_str = nascopy_config[script_path_name]
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

        self.__logger.info("nascopy script: %s", script_path)
        self.__script_path = script_path

        return True

    def should_nascopy(self):
        if self.__script_path:
            return True

        return False

    def do_nascopy(self):
        command = [self.__script_path]

        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

        def check_std(std, loglevel):
            while True:
                output = std.readline()
                if output:
                    self.__logger.log(loglevel, output.strip())
                else:
                    break

        def check_io():
            check_std(proc.stdout, logging.INFO)

        while proc.poll() is None:
            check_io()
            proc.wait()

        if proc.returncode != 0:
            return False, "nascopy script had an error. Check the logs"

        return True, None


def run(config):
    logger = logging.getLogger("nascopy")
    logger.info("NAS Copy started")

    nascopy = NasCopy(config)

    if nascopy.should_nascopy():
        status, msg = nascopy.do_nascopy()
        if not status:
            logger.error(msg)
    else:
        logger.info("NAS copy is not configured")

    logger.info("NAS copy to Phanas done")
