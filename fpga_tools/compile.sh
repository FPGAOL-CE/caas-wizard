#!/bin/bash
# File              : compile.sh
# License           : GPL-3.0-or-later
# Author            : Peter Gu <github.com/regymm>
# Date              : 2023.03.25
# Last Modified Date: 2023.04.07

if [[ "$UID" != "0" ]]; then
	echo 'This should run in Docker as root!'
	exit 1
fi

source /opt/conda/etc/profile.d/conda.sh
conda activate xc7
cp -a /mnt/* /tmp
make -C /tmp

retval=$?

cp /tmp/build/top.log /mnt


# a hack to check if OOM-ed
grep -E '(Killed|KILL)' /tmp/build/top.log && exit 233

if [[ "$retval" == "0" ]]; then
    cp /tmp/build/top.bit /mnt
	exit 0
else
	exit 1
fi
