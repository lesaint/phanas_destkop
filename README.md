# PhanNAS Desktop

Desktop integration for my NAS.

This is in no way intended to be generic.
The project is public only because it contains no sensitive information and makes cloning easier.

## requirements

### to run with a GUI

The following are required by default, unless option --no-gui is provided:
* host `nas` is defined on the machine
* python 3 installed with `gi`, `PyGObject` and `GTK 3.0`
   ```
   sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0
   ```
### on Linux

The following are required to mount NAS drives on Linux

* package `cifs-utils` installed
	* `sudo apt-get install cifs-utils`

  * directory `/__NAS__` must exist
    `sudo mkdir /mnt/__NAS__ && sudo chmod o+wx /mnt/__NAS__`
* an authentication file `{clone_directory}/.smb_phanas` exists, *with 600 permission* and the following content:
    ```
    username=XXXX
    password=YYYY
    ```
* sudoers is configured to allow `mount` and `umount` of the drives without authentication
	* use `phanas_desktop.py --generate-sudoers` to produce the required sudoers configuration for the current Linux user

### to synchronize keyfiles

The following are required to synchronize remote keyfiles stored on NAS with a local copy:
* host `nas` is defined on the machine
* KeePassXC
  * snap package is most up to date: `snap install keepassxc`

## how to use on Linux

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
	* mounting under `/mnt` is required to allow SNAP based applications (such as VLC) to access NAS drives
4. create directory `$HOME/__NAS__` and create symlinks to each mounted drive
5. TODO: add directory `$HOME/__NAS__` to Nautilus's bookmarks
7. synchronize keyfiles (if configured)
8. execute a [rsync-time-backup](https://github.com/lesaint/rsync-time-backup) (RTB) based backup script (if configured)
8. execute a [NAS Copy](https://github.com/lesaint/nascopy) based script (if configured)
6. automatically close the windows 3 seconds after successful completion

## how to configure

Create a file `{clone_directory}/config.phanas`, which contains a JSON object to configure PhanNAS.

Entries:

* `keepass.keyfile`: name of the keypass file to synchronize (location on NAS is hardcoded, local location is hardcoded to `~`)
* `backup.script_path`: path to the RTB based backup script to execute
* `nascopy.script_path`: path to the NAS copy script to execute

Sample

```json
{
  "keepass": {
    "keyfile": "foo.kdbx"
  },
  "backup": {
    "script_path": "/home/donut/scripts/backup_donut.sh"
  },
  "nascopy": {
    "script_path": "/home/donut/scripts/nascopy/nascopy_donut.sh"
  }
}
```

# License

Apache 2
