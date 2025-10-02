from pathlib import Path


class Credentials:
    def __init__(self, credential_file_path: Path):
        self.credentials_file_path = credential_file_path
        self.is_legacy_credentials_file: bool = False
        self.username: str | None = None
        self.password: str | None = None
        self.keyfile_passwords: dict[str, str] = {}

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
                    self.keyfile_passwords[parsed_line[0]] = parsed_line[1]

        # Legacy password file
        if self.username or self.password:
            self.is_legacy_credentials_file = True
            if not self.username:
                return "Missing username in credentials file"
            if not self.password:
                return "Missing password in credentials file"
            if self.keyfile_passwords:
                return "Can't mix legacy mode and providing per keyfile passwords"

        return None

    @staticmethod
    def _mask(s: str) -> str | None:
        if s is None:
            return None
        if s:
            return f"'{'*' * len(s)}'"
        return "''"

    def __str__(self):
        return (
            f"{self.credentials_file_path}: username={self.username}, password={self._mask(self.password)}, "
            f"legacy={self.is_legacy_credentials_file}, "
            f"keyfile_passwords=[{','.join([f"{k}:{self._mask(v)}" for k, v in self.keyfile_passwords.items()])}]"
        )
