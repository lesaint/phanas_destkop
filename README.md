# PhanNAS Desktop

Desktop integration for my NAS.

This is in no way intended to be generic.
The project is public only because it contains no sensitive information and makes cloning easier.

## requirements

* package `cifs-utils` installed
	* `sudo apt-get install cifs-utils`
* python 3 installed with `gi`, `PyGObject` and `GTK 3.0`
   ```
   sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
   ```
* KeePassXC
	* snap package is most up to date: `snap install keepassxc`
* host `nas` is defined on the machine
* directory `/__NAS__` must exist
	* `sudo mkdir /mnt/__NAS__ && sudo chmod o+wx /mnt/__NAS__`
* an authentication file `{clone_directory}/.smb_phanas` exists, *with 600 permission* and the following content:
    ```
    username=XXXX
    password=YYYY
    ```
* sudoers is configured to allow `mount` and `umount` of the drives without authentication
	* use `phanas_desktop.py --generate-sudoers` to produce the required sudoers configuration for the current Linux user
	* `sudo EDITOR=/usr/bin/vim visudo /etc/sudoers` and append at the end

## how to use

Add `phanas_desktop.py` to Gnome's startup programs:
* `ALT+F2`, input `gnome-session-properties`
* add startup program:
	* Name: `PhanNas Desktop`
	* Command: `/home/{username}/scripts/phanas_desktop/phanas_desktop.py`
	* Comment: (empty)

It will:

1. spawn a minimal GTK+ window showing progress status and errors if any
2. check NAS is online
3. mount NAS drives to directories `/mnt/__NAS__/{username}/{drive_name}`
	* mounting outside `$HOME` is required to avoid Nautilus loading the mounts and slowing down Gnome's login
4. create directory `$HOME/__NAS__` and create symlinks to each mounted drive
5. TODO: add directory `$HOME/__NAS__` to Nautilus's bookmarks
7. synchronize keyfiles if configured
8. execute a [rsync-time-backup](https://github.com/lesaint/rsync-time-backup) (RTB) based backup script
6. automatically close the windows 3 seconds after successful completion


# License

Apache 2
