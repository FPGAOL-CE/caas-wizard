***FPGAOL-CE CaaS Wizard API Access Guide***

## About

This tool handles Makefile generation and compilation of local/remote FPGA projects with flexible architecture and toolchain choices, by a given configuration file. 

## Installation

- Linux

  `pip install requests`

- Mac OS X
  `brew install python gsed`

  `pip3 install requests`

- Windows (WSL)

  TODO

## Basic Configuration

#### **caas.conf**

An INI configuration file, defaultly named `caas.conf`, need to be placed at the root directory of the project. It can include files in current directory and subdirectories, but not parent directory. 

A `[project]` section is required to specify the backend, FPGA chip part name, top module name, source and constraint files. A full example is: 

```
[project]
Backend = openxc7
Part = xc7a35tcpg236-1
Top = top
Constraint = top.xdc
Sources = *.v src/*.v *.vh include/*.vh
Misc = *.coe coe/*.coe
```

Everything except `Backend` and `Part` can be skipped if the default value, which can be found in [source code](https://github.com/FPGAOL-CE/caas-wizard/blob/main/caasw.py#L23), are to be used. 

This very minimum example compiles the project with `top` module name, using all `.v` files in current directory as source code: 

```
[project]
Backend = ice40
Part = ice40up5k-sg48
```

#### **caasw**

Then, the CaaS Wizard can be called to generate build scripts and Makefiles. 

In current directory: `caasw.py mfgen`

Overwrite existing (recommended): `caasw.py --overwrite mfgen`

> Specify custom dir/conf: `caasw.py mfgen path/to/caas.conf path/to/project`. However, specify a custom directory may cause confusion. 

Clean: `caasw.py clean`

A `Makefile.caas` will be generated, and a (readable) `run_caas.sh` script will call the Dockerized toolchain to compile the project. 

The compilation command for OpenXC7: 

```sh
docker run --pull never -it --rm -m 8G \
	-v `pwd`:/mnt \
	-v /chipdb:/chipdb \
	--tmpfs /tmp \
	regymm/openxc7 make -C /mnt -f Makefile.caas
```

Run `./run_caas.sh` will do the compilation if the required Docker container exists. 

Compile results will be in `./build` directory, named `top.bit` and `top.log`. The bitstream name can be changed by adding the, for Tang Nano's example, `Bitname = top.fs` line to the `[Project]` section. 

## Using Remote Server

Like the [FPGAOL-CE CaaS Platform](https://caas.symbioticeda.com), compilation can run on servers so users don't need local toolchain installation. In this case, a `[caas]` section can be used to specify server address: 

```
[caas]
Server = https://caas.symbioticeda.com:18888/
```

Run `caasw.py submit` will submit the project to remote compilation. Instead, the config file is copied to `.caas.conf`, a `.jobid` containing a random Job ID is created, then required files as long as `.caas.conf` is packed to `.caas_upload.zip`, which is uploaded to server. The Wizard then polls the server for status, and download bitstream/log to `./build` after finish.  

An example output from submit:

```
Preparing payload for project...
Copy config file...
'caas.conf' -> './.caas.conf'
Archive project...
	zip warning: name not matched: *.pcf
	zip warning: name not matched: *.lpf
	zip warning: name not matched: *.cst
  adding: .caas.conf (deflated 5%)
  adding: Basys3_Master.xdc (deflated 87%)
  adding: top.v (deflated 27%)
Use a new random jobID e6d80e06
Submitting to compiling server...
Using server at https://caas.symbioticeda.com:18888/
POST done.
Compilation submitted, now quering result...
Status query:  running
Status query:  running
Status query:  running
Status query:  running
Status query:  finished.succeeded
Compilation succeeded, fetching result...
Log downloaded.
Bitstream downloaded.
```

## Compile a GitHub project

A testing feature of fetching and compiling a project from GitHub. 

In the `[project]` section, add a `Gitconf` line will make this configuration recognized a remote project job. 

Specify the root directory: `Giturl = https://github.com/FPGAOL-CE/user-examples`

Specify a custom branch and subdirectory: `Giturl = https://github.com/FPGAOL-CE/user-examples/tree/main/basys3`

Then, there's two choices: 

- If the project **already includes** a CaaS configuration file, it can be used for compilation by specifying:

  ```
  Usegitconf = 1
  Gitconf = caas_filename.conf
  ```

  If the Gitconf is just `caas.conf`, the second line can be skipped. 

  In this case, options in the local directories' configuration file, like top name or backend, are **not needed**, and will be **ignored**. 

- If the project don't include any configuration, or the included one **do not need** to be used, no specific actions is needed. 

  In this case, the options in the local directories' configuration file have to be specified, and will be **copied** to the cloned remote directory. 

Then run `./caasw.py --clone --overwrite mfgen`: 

```
Git URL specified, repo: https://github.com/FPGAOL-CE/user-examples, branch: main, path in repo: ./basys3 
Clone the repo to ./user-examples...
Run GIT_TERMINAL_PROMPT=0 git clone --depth=1 -b main https://github.com/FPGAOL-CE/user-examples ./user-examples
Cloning into './user-examples'...
remote: Enumerating objects: 44, done.
remote: Counting objects: 100% (44/44), done.
remote: Compressing objects: 100% (40/40), done.
remote: Total 44 (delta 8), reused 32 (delta 1), pack-reused 0
Receiving objects: 100% (44/44), 610.14 KiB | 5.00 MiB/s, done.
Resolving deltas: 100% (8/8), done.
Use specified config(caas.conf) in repo.
Call caas-wizard in ./user-examples/./basys3...
------------
7-series FPGA family derived to be artix7
Copy build files...
'/home/petergu/FPGAOL/caas-wizard/fpga_tools/Makefile.openxc7' -> './Makefile.caas'
'/home/petergu/FPGAOL/caas-wizard/fpga_tools/openxc7.sh' -> './run_caas.sh'
Patching build files...
------------
Write dummy run_caas.sh...
Done preperation for Git URL compilation.
```

This time, the `caasw.py` literally calls itself one more time in the cloned repo. And the `run_caas.sh` is just a wrapper this time: 

```sh
#!/bin/sh
curdir=`pwd`
cd $curdir/user-examples/./basys3
./run_caas.sh
ret=$?
cd $curdir
mkdir -p build
cp -rf $curdir/user-examples/./basys3/build/* $curdir/build/
exit $ret
```

This type of compilation can also be submitted. 

**Caution**: It's not designed to put `caas.conf` with `Giturl` line in GitHub! This kind of file cannot be used remote compilation! 

## Supported Toolchains

Now, the following toolchains are supported: 

- OpenXC7: `openxc7`, for Xilinx 7-series
- Vivado: `vivado`, for Xilinx 7-series and maybe more, not available on compilation server

- Project Icestorm & Project Trellis  ICE40/ECP5: `ice40` and `ecp`, for Lattice devices
- Project Apicula: `gowin`, for Gowin devices

On the [FPGAOL-CE CaaS Platform](https://caas.symbioticeda.com) hosted by Symbiotic EDA, the FPGA Part contains a list of **ALL** supported devices. 
