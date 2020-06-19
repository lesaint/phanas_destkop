import os
import stat

###Returns tuple (success, msg, username, password)
def read_credentials_file(credential_file_path):
    if not credential_file_path.is_file():
        return False, "crediential file is missing"

    stats = credential_file_path.stat()
    # see https://stackoverflow.com/a/5337329
    if oct(stats.st_mode)[-3:] != "600":
        return False, "Permission of {} must be 600".format(credential_file_path)

    with open(credential_file_path, 'r') as f:
        user_line_prefix = "username="
        pwd_line_prefix = "password="

        user_line = f.readline()
        if not user_line.startswith(user_line_prefix):
            return False, "Wrong first line in credentials file"
        # substring without prefix nor ending line return
        username = user_line[len(user_line_prefix):-1]
        if not username:
            return False, "Missing username in credentials file"

        pwd_line = f.readline()
        if not pwd_line.startswith(pwd_line_prefix):
            return False, "Wrong second line in credentials file"
        pwd = pwd_line[len(pwd_line_prefix):-1]
        if not pwd:
            return False, "Missing password in credentials file"

        return True, None, username, pwd

def is_empty_dir(dir_path):
    try:
        next(dir_path.iterdir())
        return False
    except StopIteration as e:
        return True

def make_readonly(file_path):
    os.chmod(file_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
