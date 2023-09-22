#!/usr/bin/env python3
import sys
import os
import argparse
import configparser
import random
from pathlib import Path

local_server = 'http://127.0.0.1:18888/'
upload_file = '.caas_upload.zip'
download_file = '.caas_result.zip'
caas_armed_file = '.caas.conf'
jobid_file = '.jobid'
api_url = '/submit'
top_default = 'top'
constraint_default = '*.xdc'
sources_default = '*.v'
misc_default = ''

def getjobid():
    return '%08x' % random.randrange(16**8)

def mfgen(conf_file, proj_dir, makefile, script, overwrite):
    if overwrite == False and (os.path.isfile(script) or os.path.isfile(makefile)):
        print('File existing! Use --overwrite to overwrite')
        sys.exit(1)
    caas_conf = configparser.ConfigParser()
    caas_conf.read(conf_file)
    backend = caas_conf['project'].get('backend')
    part = caas_conf['project'].get('part')
    top = caas_conf['project'].get('top', top_default)
    constraint = caas_conf['project'].get('constraint', constraint_default)
    sources = caas_conf['project'].get('sources', sources_default)
    # We don't need to cover all cases, just let error happen later stage
    # deriving family from part name
    family = 'invalid'
    if 'xc7s' in part:
        family = 'spartan7'
    elif 'xc7a' in part:
        family = 'artix7'
    elif 'xc7k' in part:
        family = 'kintex7'
    elif 'xc7v' in part:
        family = 'virtex7'
    elif 'xc7z' in part:
        family = 'zynq7'
    # deriving F4PGA DEVICE from part name
    f4pga_device = 'invalid'
    if backend == 'f4pga':
        if 'xc7z' in part:
            f4pga_device = part[:7] + '_test'
        else:
            f4pga_device = part[:part.find('t')+1] + '_test'
    # copy the template files
    tools_dir = os.path.join(Path(__file__).parent.absolute(), 'fpga_tools')
    makefile_t = os.path.join(tools_dir, 'Makefile.' + backend)
    script_t = os.path.join(tools_dir, backend + '.sh')

def submit(conf_file, proj_dir, dryrun, newjobid):
    caas_conf = configparser.ConfigParser()
    caas_conf.read(conf_file)
    constraint = caas_conf['project'].get('constraint', constraint_default)
    sources = caas_conf['project'].get('sources', sources_default)
    misc = caas_conf['project'].get('misc', misc_default)
    print("Copy config file...")
    os.system("cp -v " + conf_file + ' ' + os.path.join(proj_dir, caas_armed_file))
    print("Archive project...")
    ret = os.system('cd ' + proj_dir + ' && \
            zip -FSr ' + upload_file + ' ' + \
            caas_armed_file + ' ' + constraint + ' ' + sources + ' ' + misc)
    if ret != 0:
        print("Error archiving project!")
        sys.exit(1)
    jobidfile = os.path.join(proj_dir, jobid_file)
    if os.path.isfile(jobidfile) and not newjobid:
        with open(jobidfile) as f:
            jobid = f.read()
        print("Use existing jobID " + jobid)
    else:
        jobid = getjobid()
        print("Use a new random jobID " + jobid)
        with open(jobidfile, 'w') as f:
            f.write(jobid)

def clean(conf_file, proj_dir):
    for i in [upload_file, download_file, jobid_file, caas_armed_file]:
        try:
            os.remove(os.path.join(proj_dir, i))
        except OSError:
            pass

if __name__ == '__main__':
    aparse = argparse.ArgumentParser(description='FPGAOL CaaS Wizard')
    aparse.add_argument('op', metavar='OP', type=str, nargs=1, help='Type of operation: mfgen, submit, clean')
    aparse.add_argument('--makefile', action='store', default='Makefile', help='mfgen - Name of generated Makefile')
    aparse.add_argument('--script', action='store', default='run.sh', help='mfgen - Name of generated compile script')
    aparse.add_argument('--overwrite', action='store_const', const=True, default=False, help='mfgen - Overwrite existing files')
    aparse.add_argument('--dryrun', action='store_const', const=True, default=False, help='submit - Prepare submission files but do not upload')
    aparse.add_argument('--newjobid', action='store_const', const=True, default=False, help='submit - Use a new random jobID')
    aparse.add_argument('conf', metavar='CONF', type=str, nargs='?', default='caas.conf', help='Configuration file (default: caas.conf)')
    aparse.add_argument('dir', metavar='DIR', type=str, nargs='?', default='.', help='Project directory (default: .)')
    args = aparse.parse_args()
    print(args)
    op = args.op[0]
    conf_file = args.conf
    proj_dir = args.dir
    mfgen_makefile = args.makefile
    mfgen_script = args.script
    mfgen_overwrite = args.overwrite
    submit_dryrun = args.dryrun
    submit_newjobid = args.newjobid
    if not os.path.isfile(conf_file):
        print('Configuration file %s not found!' % conf_file)
        sys.exit(1)
    if not os.path.exists(proj_dir):
        print('Project directory %s not found!' % proj_dir)
        sys.exit(1)
    if op == 'mfgen':
        mfgen(conf_file, proj_dir, mfgen_makefile, mfgen_script, mfgen_overwrite)
    elif op == 'submit':
        submit(conf_file, proj_dir, submit_dryrun, submit_newjobid)
    elif op == 'clean':
        clean(conf_file, proj_dir)
    else:
        print('Unknown OP:', op)
        sys.exit(1)
    # print(backend, part, top, constraint, sources, family, f4pga_device)
    # print(caas_conf.sections())
