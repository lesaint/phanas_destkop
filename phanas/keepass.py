import logging
import os
from itertools import chain

import getpass
import phanas.automount
import phanas.file_utils
import phanas.nas
import shutil
import socket
import subprocess
import sys
import tempfile

from datetime import datetime, timedelta
from pathlib import Path

from phanas.credentials import Credentials, CredentialsProvider, FileCredentialsProvider, KeyringCredentialsProvider, \
    InputProvider

_KEEPASSXC_CLI = "keepassxc-cli"
_KEEPASSXC_CLI_SNAP = "keepassxc.cli"
_MD5SUM = "md5sum"

_KEEPASS_CONFIG_JSON_OBJECT_NAME = "keepass"
_KEYFILES_CONFIG_JSON_OBJECT_NAME = "keyfiles"

_BACKUP_DATE_FORMAT = "%Y-%m-%d"
_BACKUP_TIMESTAMP_FORMAT = f"{_BACKUP_DATE_FORMAT}_%H-%M-%S"
_BACKUP_EXPIRATION_IN_DAYS = 60

_KEYFILE_DIR_NAME = "keys"
_SYNC_BACKUP_DIR_NAME = "_sync_backup"

_logger = logging.getLogger("keepass")

class KeyFile:
    def __init__(self, relative_path:str, local_path:Path, remote_path:Path):
        self.relative_path: str = relative_path
        self.name: str = relative_path.split("/")[1]
        self.parent_name: str = relative_path.split("/")[0]
        self.local_path: Path = local_path
        self.remote_path: Path = remote_path

    def local_file_exists(self) -> bool:
        return self.local_path.is_file()

    def remote_file_exists(self):
        return self.remote_path.is_file()

    def local_keyfile_directory(self):
        return self.local_path.parent

    def __str__(self):
        return f"Keyfile({self.relative_path}: {self.parent_name}, {self.name}, local_path='{self.local_path}', remote_path='{self.remote_path}')"

# Changes compared to previous code
# *
# Changes compared to previous behavior
# * support more than one keyfile
# * will create local keyfile when does not exist yet
# * expects username of current user and one password per keyfile be provided in the credentials file now
#   the standalone password is not expected anymore
#   password per keyfile is provided as line such as lesaint/sebastienlesaint.kdbx=foobar

class KeePass:
    __keyfile_password = None


    def __init__(self, config, credentials_provider: CredentialsProvider | None = None):
        self._keepass_config: dict = {}
        if _KEEPASS_CONFIG_JSON_OBJECT_NAME in config and isinstance(config.get(_KEEPASS_CONFIG_JSON_OBJECT_NAME), dict):
            self._keepass_config = config[_KEEPASS_CONFIG_JSON_OBJECT_NAME]
        else:
            _logger.info("KeePass config not found")

        self._linux_username: str = getpass.getuser()
        # see https://stackoverflow.com/a/799799
        self._hostname: str = socket.gethostname()

        self._automount_env = phanas.automount.Env()
        self._nas = phanas.nas.Nas()

        self._sys_drive_path = self._automount_env.mount_dir_path / self._nas.drive_sys()
        self._local_dir_path: Path = Path.home() / _KEYFILE_DIR_NAME
        self._remote_keyfile_dir_path = self._sys_drive_path / _KEYFILE_DIR_NAME
        # from https://stackoverflow.com/a/31867043
        script_dir = Path(sys.path[0])
        self._temp_dir_path = script_dir / ".tmp"

        self._credentials_file_path = script_dir / ".kpx_phanas"
        if credentials_provider:
            self.credentials_provider = credentials_provider
        else:
            self.credentials_provider = FileCredentialsProvider(self._credentials_file_path)
        self._credentials: Credentials | None = None

        self._legacy_keyfile: KeyFile | None = None
        self._keyfiles: list[KeyFile] | None = None
        self._load_keyfiles()

        self._linux_user_sync_backup_dir_path: Path | None = None

        self._keepassxc_cli: Path | None = None
        self._md5sum: Path | None = None

    def _load_keyfiles(self) -> bool:
        # legacy, expected only the name of the key file, relative path was hardcoded to the current authenticated user
        keyfile_name = self._keepass_config.get("keyfile")
        if not isinstance(keyfile_name, str) or not keyfile_name:
            return False
        else:
            relative_path = f"{self._linux_username}/{keyfile_name}"
            self._legacy_keyfile = self._new_keyfile_from_relative_path(relative_path=relative_path)
            self._keyfiles = [self._legacy_keyfile]

        # expect paths relative to keys directory in sys mount, such as phan/sebastienlesaint.kdbx
        keyfile_relative_paths = self._keepass_config.get(_KEYFILES_CONFIG_JSON_OBJECT_NAME)
        if not isinstance(keyfile_relative_paths, list) or not keyfile_relative_paths:
            return False
        else:
            self._keyfiles = [self._new_keyfile_from_relative_path(s.strip()) for s in keyfile_relative_paths if s]

        _logger.info("keyfiles: %s", ",".join(str(keyfile) for keyfile in self._keyfiles))

        return True

    def _new_keyfile_from_relative_path(self, relative_path:str) -> KeyFile:
        file = KeyFile(
            relative_path=relative_path,
            local_path=self._local_dir_path / relative_path,
            remote_path=self._sys_drive_path / _KEYFILE_DIR_NAME / relative_path,
        )
        _logger.info("new keyfile: %s", file)
        return file

    def should_synch_keyfiles(self):
        return self._keyfiles and any([s.remote_file_exists() for s in self._keyfiles])

    def do_sync(self) -> tuple[bool, str | None]:
        status, msg = self._check_prerequisites()
        if not status:
            return False, f"Can't synchronize keyfiles\n{msg}"

        status, msg = self._sync_files()
        if not status:
            return False, f"Can't synchronize keyfiles\n{msg}"

        return True, None

    def _check_prerequisites(self) -> tuple[bool, str | None]:
        # keepassxc-cli is installed
        self._keepassxc_cli = shutil.which(_KEEPASSXC_CLI_SNAP)
        if self._keepassxc_cli is None:
            self._keepassxc_cli = shutil.which(_KEEPASSXC_CLI)
        if self._keepassxc_cli is None:
            return False, f"Neither {_KEEPASSXC_CLI} nor {_KEEPASSXC_CLI_SNAP} is installed"
        _logger.info("keepassxc-cli found: %s", self._keepassxc_cli)

        # md5 is installed
        self._md5sum = shutil.which(_MD5SUM)
        if self._md5sum is None:
            return False, f"{_MD5SUM} is not installed"

        # NAS is online
        status, msg = self._nas.check_online()
        if not status:
            return False, msg

        # sys drive is mounted
        if not self._sys_drive_path.is_dir():
            return False, f"{self._sys_drive_path} is not a directory"
        if not os.path.ismount(self._sys_drive_path):
            return False, f"{self._sys_drive_path} is not mounted"
        # remote key dir is a directory
        if not self._remote_keyfile_dir_path.is_dir():
            return False, f"{self._remote_keyfile_dir_path} is not a directory"

        # Credentials can be loaded
        credentials, msg = self.credentials_provider.load_credentials()
        if msg:
            return False, msg
        _logger.debug("credentials: %s", credentials)
        self._credentials = credentials

        # Support for legacy credentials is dropped
        how_to_migrate_message = f"Legacy credentials file detected:\n" \
                                 f"     * change configuration under '{_KEEPASS_CONFIG_JSON_OBJECT_NAME}' to have a list of keyfiles under key '{_KEYFILES_CONFIG_JSON_OBJECT_NAME}'\n" \
                                 f"     * delete credentials file '{self._credentials_file_path}'\n" \
                                 f"     * create backup directory for the current user: {self._linux_user_sync_backup_dir_path}\n" \
                                 f"     * create local directory for keyfiles: {self._local_dir_path}"
        if self._credentials.is_legacy_credentials_file():
            return False, how_to_migrate_message

        # credentials are provided, for each keyfile
        if not credentials.is_legacy_credentials_file():
            for keyfile in self._keyfiles:
                if not credentials.get_keyfile_password(keyfile_relative_path=keyfile.relative_path):
                    return False, f"No password for '{keyfile.relative_path}' in credentials'"

        # legacy mode or new mode but not a mix
        new_config = 'keyfiles' in self._keepass_config
        if self._credentials.is_legacy_credentials_file() == new_config:
            return (
                False,
                f"Mixing legacy and new mode: credentials={self._credentials.is_legacy_credentials_file()}, config={new_config}\n" \
                "{how_to_migrate_message}"
            )

        # linux username is resolved
        if not self._linux_username:
            return False, "linux username could not be resolved"

        # local keyfiles directory exist
        if not self._local_dir_path.exists() or not self._local_dir_path.is_dir():
            return False, f"{self._local_dir_path} does not exist or is not a directory"

        # remote keyfiles exist
        for keyfile in self._keyfiles:
            if not keyfile.remote_path.is_file():
                return False, f"{keyfile.remote_path} does not exist"

        self._linux_user_sync_backup_dir_path = (
                self._remote_keyfile_dir_path / _SYNC_BACKUP_DIR_NAME / self._hostname / self._linux_username
        )

        # require backup directory for current host and linux username to exist
        # as a safety to not trigger and run unwanted for a new username
        if not self._linux_user_sync_backup_dir_path.is_dir():
            return False, f"{self._linux_user_sync_backup_dir_path} is not a directory. Create it to enable keyfile sync."

        # temp dir and local dir either do not exist (we'll create it) or are directories
        if self._temp_dir_path.exists() and not self._temp_dir_path.is_dir():
            return False, f"'{self._temp_dir_path}' is not a directory"
        if self._local_dir_path.exists() and not self._local_dir_path.is_dir():
            return False, f"'{self._local_dir_path}' is not a directory"

        # remote keyfiles exist
        for keyfile in self._keyfiles:
            # remote keyfile exists
            if not keyfile.remote_file_exists():
                return False, "{} is not a file".format(keyfile.remote_path)

        return True, None

    def _sync_files(self) -> tuple[bool, str | None]:
        need_sync, msg = self._need_sync()
        if not need_sync:
            _logger.info(f"Keyfiles do not need sync%s", msg if msg else "")
            return True, None
        elif msg:
            _logger.info(f"Keyfiles need sync%s", msg)

        if not self._temp_dir_path.exists():
            _logger.info("%s does not exists, creating it...", self._temp_dir_path)
            self._temp_dir_path.mkdir()

        success, msg = self._prepare_for_backup()
        if not success:
            return False, msg

        for keyfile in self._keyfiles:
            success, msg = self._sync_files_of_keyfile(keyfile)
            if not success:
                return False, msg

        return True, None

    def _sync_files_of_keyfile(self, keyfile) -> tuple[bool, str | None]:
        # backup local and remote keyfiles
        status, msg = self._backup_keyfiles(keyfile=keyfile)
        if not status:
            return False, msg

        # create local temp copies of remote file and local file
        with tempfile.NamedTemporaryFile(dir=self._temp_dir_path) as local_copy:
            with tempfile.NamedTemporaryFile(dir=self._temp_dir_path) as remote_copy:
                _logger.info("temp files: local '%s' => '%s', remote '%s' => '%s'",
                             keyfile.local_path, local_copy.name, keyfile.remote_path, remote_copy.name)

                shutil.copyfile(keyfile.local_path, local_copy.name)
                shutil.copyfile(keyfile.remote_path, remote_copy.name)

                # sync remote to local and the other way around
                _logger.info("merging local keyfile into remote...")
                success, msg = self.__merge_keyfiles(keyfile=keyfile, from_file=remote_copy.name, into_file=local_copy.name)
                if not success:
                    # TODO remove backups to avoid preventing new attempt to synchronize
                    return False, msg
                _logger.info("merging remote keyfile into local...")
                success, msg = self.__merge_keyfiles(keyfile=keyfile, from_file=local_copy.name, into_file=remote_copy.name)
                if not success:
                    # TODO remove backups to avoid preventing new attempt to synchronize
                    return False, msg

                # overwrite remote and local with up to date file
                shutil.copy(remote_copy.name, keyfile.remote_path)
                _logger.info("%s synchronized", keyfile.remote_path)
                shutil.copy(local_copy.name, keyfile.local_path)
                _logger.info("%s synchronized", keyfile.local_path)

                # TODO remove merge marker file (requires function to get the marker file path, tricky...)

        return True, None

    def _need_sync(self) -> tuple[bool, str | None]:
        for keyfile in self._keyfiles:
            # if local keyfile doesn't exist, need to sync
            if not keyfile.local_file_exists():
                return True, f"{keyfile.local_path} does not exist"

            latest_local_backup_path, local_timestamp = self._get_latest_backup(keyfile=keyfile, local=True)
            latest_remote_backup_path, remote_timestamp = self._get_latest_backup(keyfile=keyfile, local=False)

            # if either backup is missing, need to sync
            if latest_local_backup_path is None or latest_remote_backup_path is None:
                return True, "Either local backup or remote backup is missing"

            # if backups don't have same timestamp, need to sync
            if not local_timestamp == remote_timestamp:
                return (
                    True,
                    f"Latest backup of remote ({latest_remote_backup_path.name}) doesn't have the same timestamp "
                    f"as latest backup of local ({latest_local_backup_path.name})"
                )

            # TODO if merge marker file exists, return true

            # if content of local keyfile changed since last backup, need to sync
            if not phanas.file_utils.has_same_content(latest_local_backup_path, keyfile.local_path):
                return True, f"local keyfile '{keyfile.relative_path}' content changed"

            # if content of remote keyfile changed since last backup, need to sync
            if not phanas.file_utils.has_same_content(latest_remote_backup_path, keyfile.remote_path):
                return True, f"remote keyfile '{keyfile.relative_path}' content changed"

        return False, None

    def _get_latest_backup(self, keyfile: KeyFile, local: bool) -> tuple[Path, datetime]:
        max_date = None
        latest_backup_path = None
        pattern = f"{keyfile.parent_name}/*_{"local" if local else "nas"}_{keyfile.name}"
        _logger.debug(f"Looking for files matching pattern '{pattern} in {self._linux_user_sync_backup_dir_path}...")
        for file in self._linux_user_sync_backup_dir_path.glob(pattern):
            timestamp = self._read_timestamp_from_backup_file(file)
            if max_date is None or max_date < timestamp:
                max_date = timestamp
                latest_backup_path = file

        return latest_backup_path, max_date

    def __merge_keyfiles(self, keyfile: KeyFile, into_file: str, from_file: str):
        command = [
            self._keepassxc_cli,
            "merge",
            "--same-credentials",
            into_file,
            from_file,
        ]

        _logger.info("Running command: %s", command)
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        password = self._credentials.get_keyfile_password(keyfile_relative_path=keyfile.relative_path)
        outs, errs = proc.communicate(input=password)
        _logger.info("*********** output ***********\n%s", outs)
        _logger.info("***********  errs  ***********\n%s", errs)

        if proc.returncode != 0:
            if "Des identifiants invalides ont été fournis" in errs:
                return False, "Invalid password for keyfile '{}' or '{}'".format(into_file, from_file)
            return False, "Merge command '{}' failed, check the logs".format(" ".join(command))
        return True, None


    def _prepare_for_backup(self) -> tuple[bool, str | None]:
        status, msg = self._expire_old_backups()
        if not status:
            return False, msg

        # sync backup directory exists or we create it
        for d in [
            self._linux_user_sync_backup_dir_path.parents[1],
            self._linux_user_sync_backup_dir_path.parents[0],
            self._linux_user_sync_backup_dir_path,
        ]:
            if not d.exists():
                _logger.info("%s does not exists, creating it...", d)
                d.mkdir()
            elif not d.is_dir():
                return False, "{} is not a directory".format(d)

        return True, None

    @staticmethod
    def _make_sure_is_directory(dir_path: Path) -> tuple[bool, str | None]:
        if dir_path.exists():
            if not dir_path.is_dir():
                return False, f"{dir_path} is not a directory"
        else:
            dir_path.mkdir()

        return True, None

    def _backup_keyfiles(self, keyfile: KeyFile) -> tuple[bool, str | None]:
        timestamp = datetime.today().strftime(_BACKUP_TIMESTAMP_FORMAT)
        keyfile_backup_dir = self._linux_user_sync_backup_dir_path / keyfile.parent_name

        # make sure local and backup dir for this keyfile exist
        status, msg = self._make_sure_is_directory(keyfile_backup_dir)
        if not status:
            return False, msg
        if not keyfile.local_keyfile_directory().exists() or not keyfile.local_path.exists():
            # When local keyfile directory and/or local keyfile do not exist, create them as exact copy of remote
            keyfile.local_keyfile_directory().mkdir(exist_ok=True)
            shutil.copyfile(src=keyfile.remote_path, dst=keyfile.local_path, follow_symlinks=False)

        status, msg = self._make_sure_is_directory(keyfile.local_keyfile_directory())
        if not status:
            return False, msg

        remote_keyfile_backup_path = keyfile_backup_dir / f"{timestamp}_nas_{keyfile.name}"
        local_keyfile_backup_path = keyfile_backup_dir / f"{timestamp}_local_{keyfile.name}"

        if remote_keyfile_backup_path.exists() or local_keyfile_backup_path.exists():
            return False, f"backup file '{remote_keyfile_backup_path}' or '{local_keyfile_backup_path}' already exists"

        _logger.info("remote keyfile backup for %s is %s", keyfile.relative_path, remote_keyfile_backup_path)
        _logger.info("local keyfile backup for %s is %s", keyfile.relative_path, local_keyfile_backup_path)

        shutil.copyfile(src=keyfile.remote_path, dst=remote_keyfile_backup_path, follow_symlinks=False)
        shutil.copyfile(src=keyfile.local_path, dst=local_keyfile_backup_path, follow_symlinks=False)
        phanas.file_utils.make_readonly(remote_keyfile_backup_path)
        phanas.file_utils.make_readonly(local_keyfile_backup_path)

        return True, None

    def _expire_old_backups(self) -> tuple[bool, str | None]:
        if not self._linux_user_sync_backup_dir_path.is_dir():
            return True, None

        # iter over legacy backups and then backups in subdirectories
        for file in chain(self._linux_user_sync_backup_dir_path.glob("*.kdbx"), self._linux_user_sync_backup_dir_path.glob("*/*.kdbx")):
            day = self._read_day_from_backup_file(file)
            threshold_day = datetime.today() - timedelta(days=_BACKUP_EXPIRATION_IN_DAYS)
            if day < threshold_day:
                _logger.info("deleting old backup %s...", file)
                file.unlink()

        return True, None

    @staticmethod
    def _read_day_from_backup_file(file_path) -> datetime:
        day_str = file_path.stem[0 : len("2020-06-18")]
        return datetime.strptime(day_str, _BACKUP_DATE_FORMAT)

    @staticmethod
    def _read_timestamp_from_backup_file(file_path) -> datetime:
        timestamp_str = file_path.stem[0 : len("2020-06-18_09-32-45")]
        return datetime.strptime(timestamp_str, _BACKUP_TIMESTAMP_FORMAT)


def run(config, input_provider: InputProvider):
    logger = logging.getLogger("keepass")
    logger.info("Keepass synchronization started")

    keepass = KeePass(config=config, credentials_provider=KeyringCredentialsProvider(input_provider=input_provider))

    if keepass.should_synch_keyfiles():
        status, msg = keepass.do_sync()
        if not status:
            logger.error("Sync failed: %s", msg)
    else:
        logger.info("Keyfile synchronization is not configured")

    logger.info("Keepass synchronization done")
