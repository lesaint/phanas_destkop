#!/bin/bash

MNT_DIR=`pwd`
for i in `ls -d1 */`; do
	drive="$MNT_DIR/${i%?}"
	echo "umounting $drive..."
	sudo umount "$drive" && echo "ok"
done

