import hashlib
import json
import logging
import os
import stat
import sys

from pathlib import Path

__logger = logging.getLogger("file_utils")


def read_config_file():
    CONFIG_FILENAME = "config.phanas"
    config_file_path = Path(sys.path[0]) / CONFIG_FILENAME

    if not config_file_path.is_file():
        __logger.info("Config file %s not found", config_file_path)
        return {}

    with open(config_file_path, "r") as f:
        return json.load(f)


###Returns tuple (success, msg, username, password)
def read_credentials_file(credential_file_path):
    if not credential_file_path.is_file():
        return False, "credential file is missing", None, None

    stats = credential_file_path.stat()
    # see https://stackoverflow.com/a/5337329
    if oct(stats.st_mode)[-3:] != "600":
        return (
            False,
            "Permission of {} must be 600".format(credential_file_path),
            None,
            None,
        )

    with open(credential_file_path, "r") as f:
        user_line_prefix = "username="
        pwd_line_prefix = "password="

        user_line = f.readline()
        if not user_line.startswith(user_line_prefix):
            return False, "Wrong first line in credentials file", None, None
        # substring without prefix nor ending line return
        username = user_line[len(user_line_prefix) : -1]
        if not username:
            return False, "Missing username in credentials file", None, None

        pwd_line = f.readline()
        if not pwd_line.startswith(pwd_line_prefix):
            return False, "Wrong second line in credentials file", None, None
        pwd = pwd_line[len(pwd_line_prefix) : -1]
        if not pwd:
            return False, "Missing password in credentials file", None, None

        return True, None, username, pwd


def is_empty_dir(dir_path):
    try:
        next(dir_path.iterdir())
        return False
    except StopIteration as e:
        return True


def make_readonly(file_path):
    os.chmod(file_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def has_same_content(file_1_path, file_2_path):
    return __compute_hash(file_1_path) == __compute_hash(file_2_path)


def __compute_hash(file_path):
    # from https://nitratine.net/blog/post/how-to-hash-files-in-python/
    BLOCK_SIZE = 65536
    file_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        fb = f.read(BLOCK_SIZE)
        while len(fb) > 0:
            file_hash.update(fb)
            fb = f.read(BLOCK_SIZE)

    return file_hash.hexdigest()
