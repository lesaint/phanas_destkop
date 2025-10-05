from contextlib import closing
from pathlib import Path
from abc import ABC, abstractmethod

import secretstorage


def _mask_password(s: str) -> str | None:
    if s is None:
        return None
    if s:
        return f"'{'*' * len(s)}'"
    return "''"

class Credentials(ABC):
    @abstractmethod
    def is_legacy_credentials_file(self) -> bool:
        pass

    @abstractmethod
    def get_keyfile_password(self, keyfile_relative_path: str) -> str | None:
        pass


class CredentialsProvider(ABC):
    @abstractmethod
    def load_credentials(self) -> tuple[Credentials | None, str | None]:
        pass


class FileCredentialsProvider(CredentialsProvider):
    """
    Loads credentials from a file.
    """
    def __init__(self, credential_file_path: Path):
        self.credentials_file_path = credential_file_path

    def load_credentials(self) -> tuple[Credentials | None, str| None]:
        res: FileCredentials = FileCredentials(self.credentials_file_path)
        msg = res.load()
        if msg:
            return None, msg
        return res, None

class FileCredentials(Credentials):
    def __init__(self, credential_file_path: Path):
        self.credentials_file_path = credential_file_path
        self._is_legacy_credentials_file: bool = False
        self.username: str | None = None
        self.password: str | None = None
        self._keyfile_passwords: dict[str, str] = {}

    def is_legacy_credentials_file(self) -> bool:
        return self._is_legacy_credentials_file

    def get_keyfile_password(self, keyfile_relative_path: str) -> str | None:
        return self._keyfile_passwords.get(keyfile_relative_path)

    def load(self) -> str | None:
        if not self.credentials_file_path.is_file():
            return f"Credential file '{self.credentials_file_path}' not found"

        stats = self.credentials_file_path.stat()
        # see https://stackoverflow.com/a/5337329
        if oct(stats.st_mode)[-3:] != "600":
            return f"Permission of {self.credentials_file_path.absolute()} must be 600"

        with open(self.credentials_file_path, "r") as f:
            for line in f.readlines():
                parsed_line = [s.strip() for s in line.split("=")]
                if not parsed_line[1]:
                    # ignore empty password value
                    continue
                elif parsed_line[0] == "username":
                    self.username = parsed_line[1]
                elif parsed_line[0] == "password":
                    self.password = parsed_line[1]
                elif parsed_line[0]:
                    self._keyfile_passwords[parsed_line[0]] = parsed_line[1]

        # Legacy password file
        if self.username or self.password:
            self._is_legacy_credentials_file = True
            if not self.username:
                return "Missing username in credentials file"
            if not self.password:
                return "Missing password in credentials file"
            if self._keyfile_passwords:
                return "Can't mix legacy mode and providing per keyfile passwords"

        return None

    def __str__(self):
        return (
            f"{self.credentials_file_path}: username={self.username}, password={_mask_password(self.password)}, "
            f"legacy={self._is_legacy_credentials_file}, "
            f"keyfile_passwords=[{','.join([f"{k}:{_mask_password(v)}" for k, v in self._keyfile_passwords.items()])}]"
        )


class InputProvider(ABC):
    @abstractmethod
    def get_password(self, prompt: str) -> str | None:
        pass

class KeyringCredentialsProvider(CredentialsProvider):
    def __init__(self, input_provider: InputProvider):
        self._input_provider = input_provider

    def load_credentials(self) -> tuple[Credentials | None, str | None]:
        res = KeyringCredentials(input_provider=self._input_provider)
        msg = res.initialize()
        if msg:
            return None, msg
        return res, None


class KeyringCredentials(Credentials):
    def __init__(self, input_provider: InputProvider):
        self._keyfile_passwords: dict[str, str] = {}
        self._base_attributes: dict[str, str] = {'application': 'phanas_desktop', 'type': 'keyfile'}
        self._password_encoding: str = "utf-8"
        self._input_provider: InputProvider = input_provider

    def initialize(self) -> str | None:
        with closing(secretstorage.dbus_init()) as dbus_connection:
            return self._load_existing_keyfile_passwords(dbus_connection)

    def _load_existing_keyfile_passwords(self, dbus_connection: secretstorage.DBusConnection) -> str | None:
        collection = secretstorage.get_default_collection(dbus_connection)
        items = collection.search_items(self._base_attributes)
        for item in items:
            relative_path = item.get_attributes().get("relative_path")
            password = item.get_secret().decode(self._password_encoding)
            self._keyfile_passwords[relative_path] = password

        return None

    def _store_keyfile_password_in_keyring(self, relative_path: str, password: str):
        with closing(secretstorage.dbus_init()) as dbus_connection:
            collection = secretstorage.get_default_collection(dbus_connection)
            item_attributes = {**self._base_attributes, "relative_path": relative_path}
            collection.create_item(
                label=f"PhanNAS Desktop : keyfile password : {relative_path}",
                attributes=item_attributes,
                secret=password.encode(self._password_encoding),
            )

    def  is_legacy_credentials_file(self) -> bool:
        return False

    def get_keyfile_password(self, keyfile_relative_path: str) -> str | None:
        password = self._keyfile_passwords.get(keyfile_relative_path)
        if password:
            return password

        password = self._input_provider.get_password(prompt=f"Provide password for keyfile '{keyfile_relative_path}': ")
        if password:
            self._keyfile_passwords[keyfile_relative_path] = password
            self._store_keyfile_password_in_keyring(relative_path=keyfile_relative_path, password=password)
            return password

        return None

