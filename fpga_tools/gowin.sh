#!/bin/bash -ex
if [[ $(uname -m) == "aarch64" ]]; then
	append="-arm"
else
	append=""
fi

${DOCKER_EXEC:-docker} run --pull never -it --rm -m 8G \
	-v `pwd`:/mnt \
	--tmpfs /tmp \
	--user root \
	regymm/gowin${append} make -C /mnt -f Makefile.caas
