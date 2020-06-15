#!/bin/bash

MNT_DIR="/__NAS__"

cd "$MNT_DIR"
for i in `ls -d1 */`; do
	drive=${i%?}
	echo "$drive:"
	sudo umount "$MNT_DIR/$drive"
done

