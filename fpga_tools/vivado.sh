#!/bin/bash -ex

docker run --pull never -it --rm -m 8G \
	-v `pwd`/$workroot:/mnt \
	--tmpfs /tmp \
	regymm/vivado-lite make -C /mnt -f Makefile.caas
