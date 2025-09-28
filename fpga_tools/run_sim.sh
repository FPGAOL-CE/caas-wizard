#!/bin/bash -ex

# Simulation mode script for FPGAOL CaaS
# This script runs simulation instead of compilation

# Check if we're on ARM64 architecture
if [[ $(uname -m) == "aarch64" ]]; then
	append="-arm"
else
	append=""
fi

# Run simulation using OSS CAD Suite container
# This container includes Verilator, Icarus Verilog, and other simulation tools
${DOCKER_EXEC:-docker} run --pull never -it --rm -m 8G \
	-v `pwd`:/mnt \
	--tmpfs /tmp \
	regymm/oss-cad-suite${append} make -C /mnt -f Makefile.sim.caas