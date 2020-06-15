# PhanNAS Desktop

Desktop integration for my NAS.

This is in no way intended to be generic.
The project is public only because it contains no sensitive information and makes cloning easier.

## requirements

* host `nas` is defined on the machine
* directory `/__NAS__` must exist
* an authentication file `{clone_directory}/.phanas` exists, *with 600 permission* and the following content:
    ```
    username=XXXX
    password=YYYY
    ```
* sudoers is configured to allow `mount` and `umount` of the drives without authentication
	* use `phanas_desktop.py --generate-sudoers` to produce the required sudoers configuration for the current Linux user and NAS user from the authentication file

## how to use

Add `phanas_desktop.py` to Gnome's startup programs, it will:

1. spawn a minimal GTK+ window showing progress status and errors if any
2. check NAS is online
3. mount NAS drives to directories `/__NAS__/{nas_username}/{drive_name}`
	* this way the same drives can be mounted with different NAS users
4. create directory `$HOME/__NAS__` and create symlinks to each mounted drive, this:
	* avoids Nautilus mounting the drive and slowing down Gnome login
	* allow sharing the same mounted drive between users (currently not used)
	* while still making the drive easily accessible
5. add directory `$HOME/__NAS__` to Nautilus's bookmarks


# License

Apache 2