#!/usr/bin/env python3
import sys
import os
import time
import random
import argparse
import configparser
import requests
import urllib.parse
import json
from pathlib import Path

local_server = 'http://127.0.0.1:18888/'
upload_file = '.caas_upload.zip'
download_file = '.caas_result.zip'
caas_armed_file = '.caas.conf'
jobid_file = '.jobid'
result_dir = 'build'
result_log_name = 'top.log'
result_bit_name = 'top.bit'
api_url = '/submit'
top_default = 'top'
constraint_default = '*.xdc'
sources_default = '*.v'
misc_default = ''

term_white = "\033[37m"
term_orig = "\033[0m"

GENERIC_MF_NAME = 'Makefile.caas'
GENERIC_SH_NAME = 'run_caas.sh'

def xc7family_derive(part, backend):
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
    print("7-series FPGA family derived to be " + family)
    return family

def f4pga_device_derive(part, backend):
    f4pga_device = 'invalid'
    if backend == 'f4pga':
        if 'xc7z' in part:
            f4pga_device = part[:7] + '_test' # now seems xc7z010 only
        else:
            f4pga_device = part[:part.find('t')+1] + '_test'
        print("F4PGA device name derived to be " + f4pga_device)
    return f4pga_device

def ecp5_derive(part, backend):
    ecp5_part = 'invalid'
    ecp5_package = 'invalid'
    if backend == 'yosyshq' and 'lfe5' in part:
        prefix = 'um5g-' if 'um5g' in part else 'um-' if 'um' in part else ''
        size = ''
        if '12f' in part:
            size = '12k'
        elif '25f' in part:
            size = '25k'
        elif '45f' in part:
            size = '45k'
        elif '85k' in part:
            size = '85k'
        ecp5_part = prefix + size
        if '256' in part:
            ecp5_package = 'CABGA256'
        elif '285' in part:
            ecp5_package = 'CSFBGA285'
        elif '381' in part:
            ecp5_package = 'CABGA381'
        elif '554' in part:
            ecp5_package = 'CABGA554'
        elif '756' in part:
            ecp5_package = 'CABGA756'
        elif '144' in part:
            ecp5_package = 'TQFP144'
    return (ecp5_part, ecp5_package)

def ice40_derive(part, backend):
    ice40_part = 'invalid'
    ice40_package = 'invalid'
    if backend == 'yosyshq' and 'ice40' in part:
        ice40_part = part[5:part.find('-')]
        if ice40_part[0] == 'p':
            ice40_part[0] = 'u'
        ice40_package = part[part.find('-')+1:]
    return (ice40_part, ice40_package)

def getjobid():
    return '%08x' % random.randrange(16**8)

# this runs on the compiling server
def mfgen(conf_file, proj_dir, makefile, script, overwrite):
    if overwrite == False and (os.path.isfile(script) or os.path.isfile(makefile)):
        print('File exist! Use --overwrite to overwrite')
        sys.exit(1)
    caas_conf = configparser.ConfigParser()
    caas_conf.read(conf_file)
    backend = caas_conf['project'].get('backend')
    part = caas_conf['project'].get('part')
    top = caas_conf['project'].get('top', top_default)
    constraint = caas_conf['project'].get('constraint', constraint_default)
    sources = caas_conf['project'].get('sources', sources_default)

    # We don't need to cover all cases, just let error happen later stage

    # deriving family from part name for 7-series
    xc7family = xc7family_derive(part, backend)

    # deriving F4PGA DEVICE from part name
    f4pga_device = f4pga_device_derive(part, backend)
    
    # deriving ecp5 compilation options
    ecp5_part, ecp5_package = ecp5_derive(part, backend)

    # deriving ice40 compilation options
    ice40_part, ice40_package = ice40_derive(part, backend)

    # copy the template files
    print("Copy build files...")
    tools_dir = os.path.join(Path(__file__).parent.absolute(), 'fpga_tools')
    mf_t = os.path.join(tools_dir, 'Makefile.' + backend)
    sh_t = os.path.join(tools_dir, backend + '.sh')
    mf = os.path.join(proj_dir, GENERIC_MF_NAME)
    sh = os.path.join(proj_dir, GENERIC_SH_NAME)
    os.system("cp -v " + mf_t + " " + mf)
    os.system("cp -v " + sh_t + " " + sh)

    print("Patching build files...")
    srcwildcard = ""
    # only vivado backend is tcl-based, others are just makefiles
    if backend != 'vivado':
        for s in sources.replace("/", "\/").split(","):
            srcwildcard = srcwildcard + " $(wildcard " + s + ") "
    else:
        srcwildcard = sources.replace("/", "\/").replace(",", " ")
    os.system("sed -i " 
              + "-e \'s/__CAAS_TOP/" + top + "/g\' "
              + "-e \'s/__CAAS_SOURCES/" + srcwildcard + "/g\' "
              + "-e \'s/__CAAS_XDC/" + constraint.replace("/", "\/") + "/g\' "
              + "-e \'s/__CAAS_PART/" + part + "/g\' "
              + "-e \'s/__CAAS_FAMILY/" + xc7family + "/g\' "
              + "-e \'s/__CAAS_F4PGA_DEVICE/" + f4pga_device + "/g\' "
              + "-e \'s/__CAAS_ECP5_PART/" + ecp5_part + "/g\' "
              + "-e \'s/__CAAS_ECP5_PACKAGE/" + ecp5_package + "/g\' "
              + "-e \'s/__CAAS_ICE40_PART/" + ice40_part + "/g\' "
              + "-e \'s/__CAAS_ICE40_PACKAGE/" + ice40_package + "/g\' "
              + mf)

def requestexp(e):
    print("Exception occured when communicating with server: ", e)

def submit(conf_file, proj_dir, dryrun, newjobid):
    print(term_white + "Preparing payload for project..." + term_orig)
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
            caas_armed_file + ' ' + constraint.replace(",", " ") + ' ' + sources.replace(",", " ") + ' ' + misc.replace(",", " "))
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
    if dryrun:
        print("Dryrun, stop here.")
        return
    print(term_white + "Submitting to compiling server..." + term_orig)
    server = caas_conf['caas'].get('server', local_server)
    print("Using server at " + server)
    server_submit = urllib.parse.urljoin(server, 'submit')
    server_status = urllib.parse.urljoin(server, 'status/' + str(jobid))
    server_bit_dl = urllib.parse.urljoin(server, 'download/' + str(jobid) + '/bitstream')
    server_log_dl = urllib.parse.urljoin(server, 'download/' + str(jobid) + '/log')
    try:
        response = requests.post(server_submit,
                                 data={'inputJobId': jobid},
                                 files={'inputZipFile': ('job.zip',
                                                         open(os.path.join(proj_dir, upload_file), 'rb'),
                                                         'application/zip')})
    except Exception as e:
        requestexp(e)
        return

    if response.status_code == 200:
        print("POST done.")
        reply = json.loads(response.text)
        if reply['code'] == '0':
            print("Compilation cannot be submitted: ", reply['msg'])
            return
        else:
            print(term_white + "Compilation submitted, now quering result..." + term_orig)
    else:
        print("POST failed with code", response.status_code)
        return

    status = 'undefined'
    interval = 2
    count = 0
    errcnt = 0
    while True: 
        count = count + 1
        if count > 3:
            interval = 5
        elif count > 6:
            interval = 10
        if errcnt > 3:
            print(term_white + "Network error when fetching result." + term_orig)
            return
        time.sleep(interval)
        try:
            response = requests.get(server_status)
        except Exception as e:
            requestexp(e)
            errcnt = errcnt + 1
            continue
        if response.status_code == 200:
            print("Status query: ", response.text)
            if not 'running' in response.text:
                status = response.text
                break
        else:
            print("Status query GET failed with code", response.status_code)
            errcnt = errcnt + 1
            continue

    success = 'succeeded' in status
    if not success:
        print(term_white + "Compilation failed." + term_orig)
    else:
        print(term_white + "Compilation succeeded, fetching result..." + term_orig)

    try:
        response = requests.get(server_log_dl)
        if response.status_code == 200:
            result_dir_abs = os.path.join(proj_dir, result_dir)
            if not os.path.exists(result_dir_abs):
                os.makedirs(result_dir_abs)
            with open(os.path.join(result_dir_abs, result_log_name), "wb") as f:
                f.write(response.content)
            print(term_white + "Log downloaded." + term_orig)
        else:
            print("Request failed: ", response.status_status)
    except Exception as e:
        requestexp(e)

    if not success:
        return

    try:
        response = requests.get(server_bit_dl)
        if response.status_code == 200:
            result_dir_abs = os.path.join(proj_dir, result_dir)
            if not os.path.exists(result_dir_abs):
                os.makedirs(result_dir_abs)
            with open(os.path.join(result_dir_abs, result_bit_name), "wb") as f:
                f.write(response.content)
            print(term_white + "Bitstream downloaded." + term_orig)
        else:
            print("Request failed: ", response.status_status)
    except Exception as e:
        requestexp(e)


def clean(conf_file, proj_dir):
    for i in [upload_file, download_file, jobid_file, caas_armed_file]:
        try:
            os.remove(os.path.join(proj_dir, i))
        except OSError:
            pass
    print("Temp files cleaned for project ", proj_dir)

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
