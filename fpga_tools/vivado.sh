#!/bin/bash -ex
# File              : f4pga.sh
# License           : GPL-3.0-or-later
# Author            : Peter Gu <github.com/regymm>
# Date              : 2023.03.25
# Last Modified Date: 2023.04.07

workroot=$1
simplejob=$2
device=$3
topname=$4
xdcfile=$5
srcfile1=$6

if [[ "$simplejob" != "1" ]]; then
	echo 'Only simple job is support now!'
	exit 1
fi

cp fpga_tools/compile.openxc7.sh $workroot/compile.sh
cp fpga_tools/Makefile.openxc7 $workroot/Makefile
docker run -it --rm -m 8G \
	-v `pwd`/$workroot:/mnt \
	-v /chipdb:/chipdb \
	--tmpfs /tmp \
	regymm/openxc7 /mnt/compile.sh $device $topname
