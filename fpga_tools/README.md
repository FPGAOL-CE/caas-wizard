## makefile-gen
Generate Makefile and script from CaaS configuration file. 

**Convention**
Compiling results and temporary files should be generated in and only in the `./build` directory. 
The template files named `Makefile.backend` and `backend.sh` will be copied into the project directory as generic `Makefile` and `run.sh`, and the contents will be updated with correct parameters. 
