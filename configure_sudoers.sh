#!/bin/bash
#
# This script create the sudoers permissions required by PhanDesktop's automount feature
# by creating a file in /etc/sudoers.d named phan_desktop_automount
# 
# The script overwrites the file if it already exists, after dumping its content
# to stdout
#

set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
SUDOERS_FILE="/etc/sudoers.d/phan_desktop_automount_$USER"

echo "Creating $SUDOERS_FILE..."
if [ -f "$SUDOERS_FILE" ]; then
	echo "  File already exists, printing and overwriting..."
	sudo cat "$SUDOERS_FILE"
	sudo rm "$SUDOERS_FILE"
fi
# source for writing sudoers file and changing permissions: https://doc.ubuntu-fr.org/sudoers#etcsudoersd
# source to redirect output and write it as root: https://stackoverflow.com/a/8213307
"$BASE_DIR/phanas_desktop.py" --generate-sudoers | sudo dd of=$SUDOERS_FILE && sudo chmod 440 "$SUDOERS_FILE"

