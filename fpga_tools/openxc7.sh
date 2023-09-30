#!/bin/bash -ex

docker run -it --rm -m 8G \
	-v `pwd`:/mnt \
	-v /chipdb:/chipdb \
	--tmpfs /tmp \
	regymm/openxc7 make -C /mnt
