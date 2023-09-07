#!/bin/bash
# File              : compile.openxc7.sh
# License           : GPL-3.0-or-later
# Author            : Peter Gu <github.com/regymm>
# Date              : 2023.04.14
# Last Modified Date: 2023.04.23

if [[ "$UID" != "0" ]]; then
	echo 'This should run in Docker as root!'
	exit 1
fi

device=$1
topname=$2

logfile="/tmp/top.log"
bitfile="/tmp/top.bit"

if [[ "$device" == "xc7a"* ]]; then
	fam="artix7"
elif [[ "$device" == "xc7k"* ]]; then
	fam="kintex7"
elif [[ "$device" == "xc7s"* ]]; then
	fam="spartan7"
elif [[ "$device" == "xc7v"* ]]; then
	fam="virtex7"
else
	echo "Unable to derive family from device name $device!" >> $logfile
	exit 1
fi

source /prjxray/env/bin/activate

cp -a /mnt/* /tmp
PART=$device CHIPFAM=$fam TOP=$topname make -C /tmp

retval=$?

cp $logfile /mnt

# a hack to check if OOM-ed
grep -E '(Killed|KILL)' $logfile && exit 233

if [[ "$retval" == "0" ]]; then
    cp $bitfile /mnt
	exit 0
else
	exit 1
fi
