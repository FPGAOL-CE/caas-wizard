#!/bin/bash -ex
if [[ $(uname -m) == "aarch64" ]]; then
	append="-arm"
else
	append=""
fi

docker run --pull never -it --rm -m 8G \
	-v `pwd`:/mnt \
	--tmpfs /tmp \
	regymm/gowin-gocd${append} make -C /mnt -f Makefile.caas
