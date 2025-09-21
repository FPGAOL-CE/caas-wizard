#!/usr/bin/env python3
import sys
import os
import time
import random
import argparse
import configparser
import urllib.parse
import json
import re
from pathlib import Path

local_server = 'http://127.0.0.1:18888/'
upload_file = '.caas_upload.zip'
download_file = '.caas_result.zip'
caas_armed_file = '.caas.conf'
jobid_file = '.jobid'
result_dir = 'build'
result_log_name = 'top.log'
result_bit_name = 'top.bit'
# api_url = '/submit'

# the default entries, these are important
top_default = 'top'
constraint_default = '*.xdc,*.pcf,*.lpf,*.cst'
sources_default = '*.v'
misc_default = ''
bitname_default = 'top.bit'
caas_conf_default = 'caas.conf'
simtop_default = '' # this is empty, so Makefile will automatically pick a top
waveform_default = 'wave.vcd'

term_white = "\033[37m"
term_orig = "\033[0m"

SEDEXEC = 'gsed' if sys.platform == 'darwin' else 'sed'

GENERIC_MF_NAME = 'Makefile.caas'
GENERIC_SH_NAME = 'run_caas.sh'
GENERIC_SIM_SH_NAME = 'run_sim.sh'
GENERIC_SIM_MF_NAME = 'Makefile.sim.caas'

def validate_basic_field(value, field_name):
    """Validate fields that allow only alphanumeric, underscore, and minus sign"""
    if value is None:
        return True  # None values are handled by defaults
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        print(f'Error: {field_name} contains invalid characters. Only 0-9, a-z, A-Z, underscore, and minus sign are allowed.')
        print(f'Invalid value: {value}')
        return False
    return True

def validate_filename_field(value, field_name):
    """Validate fields that allow alphanumeric, underscore, minus sign, and period (for filenames)"""
    if value is None:
        return True  # None values are handled by defaults
    if not re.match(r'^[a-zA-Z0-9_.-]+$', value):
        print(f'Error: {field_name} contains invalid characters. Only 0-9, a-z, A-Z, underscore, minus sign, and period are allowed.')
        print(f'Invalid value: {value}')
        return False
    return True

def validate_file_pattern_field(value, field_name):
    """Validate fields that allow alphanumeric, underscore, minus sign, and asterisk"""
    if value is None or value == '':
        return True  # None/empty values are handled by defaults
    if not re.match(r'^[a-zA-Z0-9_*,.\/-]+$', value):
        print(f'Error: {field_name} contains invalid characters. Only 0-9, a-z, A-Z, underscore, minus sign, asterisk, comma, period, slash, and minus are allowed.')
        print(f'Invalid value: {value}')
        return False
    return True

def validate_part_field(value, field_name):
    """Validate part field that allows alphanumeric, underscore, minus sign, slash, and backslash"""
    if value is None:
        print(f'Error: {field_name} is required but not specified in configuration file.')
        return False
    if not re.match(r'^[a-zA-Z0-9_\-/\\]+$', value):
        print(f'Error: {field_name} contains invalid characters. Only 0-9, a-z, A-Z, underscore, minus sign, slash, and backslash are allowed.')
        print(f'Invalid value: {value}')
        return False
    return True

def validate_url_field(value, field_name):
    """Validate URL fields (giturl) - basic validation for common URL characters"""
    if value is None or value == '':
        return True  # Optional field
    # Allow common URL characters: alphanumeric, underscore, minus, period, slash, colon, question mark, equals, ampersand
    if not re.match(r'^[a-zA-Z0-9_\-.:/?=&]+$', value):
        print(f'Error: {field_name} contains invalid characters for a URL.')
        print(f'Invalid value: {value}')
        return False
    return True

def validate_config_values(caas_conf, backend_override=None):
    """Validate all configuration values for special characters"""
    valid = True
    
    # Get values from config
    backend = backend_override if backend_override else caas_conf['project'].get('backend')
    part = caas_conf['project'].get('part')
    top = caas_conf['project'].get('top', top_default)
    constraint = caas_conf['project'].get('constraint', constraint_default)
    sources = caas_conf['project'].get('sources', sources_default)
    bitname = caas_conf['project'].get('bitname', bitname_default)
    misc = caas_conf['project'].get('misc', misc_default)
    giturl = caas_conf['project'].get('giturl')
    gitconf = caas_conf['project'].get('gitconf', caas_conf_default)
    
    # Validate basic fields (alphanumeric, underscore, minus only)
    valid &= validate_basic_field(backend, 'backend')
    valid &= validate_basic_field(top, 'top')
    
    # Validate filename fields (allow period for file extensions)
    valid &= validate_filename_field(bitname, 'bitname')
    valid &= validate_filename_field(gitconf, 'gitconf')
    
    # Validate part field (includes slash and backslash)
    valid &= validate_part_field(part, 'part')
    
    # Validate file pattern fields (includes asterisk)
    valid &= validate_file_pattern_field(constraint, 'constraint')
    valid &= validate_file_pattern_field(sources, 'sources')
    valid &= validate_file_pattern_field(misc, 'misc')
    
    # Validate URL field
    valid &= validate_url_field(giturl, 'giturl')
    
    # Validate simulation fields if present
    if 'sim' in caas_conf:
        sim_top = caas_conf['sim'].get('top', simtop_default)
        sim_sources = caas_conf['sim'].get('sources', sources)
        sim_misc = caas_conf['sim'].get('misc', misc)
        sim_vcd = caas_conf['sim'].get('vcd', waveform_default)
        
        valid &= validate_basic_field(sim_top, 'sim.top') if sim_top else True
        valid &= validate_file_pattern_field(sim_sources, 'sim.sources')
        valid &= validate_file_pattern_field(sim_misc, 'sim.misc')
        valid &= validate_file_pattern_field(sim_vcd, 'sim.vcd')
    
    return valid

def xc7family_derive(part, backend):
    family = ''
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
    f4pga_device = ''
    if backend == 'f4pga':
        if 'xc7z' in part:
            f4pga_device = part[:7] + '_test' # now seems xc7z010 only
        else:
            f4pga_device = part[:part.find('t')+1] + '_test'
        print("F4PGA device name derived to be " + f4pga_device)
    return f4pga_device

def ecp5_derive(part, backend):
    ecp5_part = ''
    ecp5_package = ''
    if backend == 'ecp5' and 'lfe5' in part:
        prefix = 'um5g-' if 'um5g' in part else 'um-' if 'um' in part else ''
        size = ''
        if '12f' in part:
            size = '12k'
        elif '25f' in part:
            size = '25k'
        elif '45f' in part:
            size = '45k'
        elif '85f' in part:
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
    ice40_part = ''
    ice40_package = ''
    if backend == 'ice40' and 'ice40' in part:
        ice40_part = part[5:part.find('-')]
        if ice40_part[0] == 'p':
            ice40_part[0] = 'u'
        ice40_package = part[part.find('-')+1:]
    return (ice40_part, ice40_package)

def gowin_derive(part, backend):
    gowin_part = ''
    gowin_family = ''
    if backend == 'gowin' and 'GW' in part:
        gowin_part = part
        # parts in https://github.com/YosysHQ/apicula/blob/master/examples/Makefile
        if part == 'GW1NR-LV9QN88PC6\/I5':
            gowin_family = 'GW1N-9C'
        elif part == 'GW1NSR-LV4CQN48PC7\/I6':
            gowin_family = 'GW1NS-4'
        elif part == 'GW1NZ-LV1QN48C6\/I5':
            gowin_family = 'GW1NZ-1'
        elif part == 'GW1NR-LV9QN88C6\/I5':
            gowin_family = 'GW1N-9'
        elif part == 'GW2AR-LV18QN88C8\/I7':
            gowin_family = 'GW2A-18C'
        elif part == 'GW2A-LV18PG256C8\/I7':
            gowin_family = 'GW2A-18'
        elif part == 'GW1N-UV4LQ144C6\/I5':
            gowin_family = 'GW1N-4'
        elif part == 'GW1N-LV1QN48C6\/I5':
            gowin_family = 'GW1N-1'
        elif part == 'GW1NS-UX2CQN48C5\/I4':
            gowin_family = 'GW1NS-2'
    return (gowin_part, gowin_family)

def getjobid():
    return '%08x' % random.randrange(16**8)

# this is writen by GPT
def extract_github_url(url):
    pattern = re.compile(r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)(?:/tree/(?P<branch>[^/]+)/(?P<dir>.+))?")
    match = pattern.search(url)
    
    if match:
        owner_repo = f"https://github.com/{match.group('owner')}/{match.group('repo')}"
        branch = match.group('branch') or ""
        dir_path = match.group('dir') or "."
        # Format dir_path to start with './' indicating current/selected directory
        dir_path_formatted = f"./{dir_path}" if not dir_path.startswith('.') else dir_path
        localdir = match.group('repo')
        return (owner_repo, branch, dir_path_formatted, localdir)
    else:
        return (-1, -1, -1, -1)

def git_clone(url, branch, dir):
    cmd = "GIT_TERMINAL_PROMPT=0 git clone --depth=1 " + (("-b " + branch) if branch else "") + " " + url + " " + dir
    print('Run ' + cmd)
    return os.system(cmd)

# this runs on the compiling server, caasw submit doesn't need this
def mfgen(conf_file, proj_dir, makefile, script, backend, overwrite, clone, sim=False):
    if overwrite == False and (os.path.isfile(script) or os.path.isfile(makefile)):
        print('File exist! Use --overwrite to overwrite')
        sys.exit(1)
    caas_conf = configparser.ConfigParser()
    caas_conf.read(conf_file)

    # Validate configuration values for special characters
    if not validate_config_values(caas_conf, backend):
        print('Configuration input validation failed! Please fix the invalid characters in your configuration file.')
        sys.exit(1)

    backend = caas_conf['project'].get('backend') if backend == None else backend
    part = caas_conf['project'].get('part')
    top = caas_conf['project'].get('top', top_default)
    constraint = caas_conf['project'].get('constraint', constraint_default)
    sources = caas_conf['project'].get('sources', sources_default)
    bitname = caas_conf['project'].get('bitname', bitname_default)
    misc = caas_conf['project'].get('misc', misc_default)
    giturl = caas_conf['project'].get('giturl')
    usegitconf = caas_conf['project'].get('usegitconf')
    gitconf = caas_conf['project'].get('gitconf', caas_conf_default)
    
    # Handle simulation-specific configuration
    if 'sim' in caas_conf:
        sim_top = caas_conf['sim'].get('top', simtop_default)
        sim_sources = caas_conf['sim'].get('sources', sources)
        sim_misc = caas_conf['sim'].get('misc', misc)
        sim_vcd = caas_conf['sim'].get('vcd', waveform_default)
    else:
        sim_top = simtop_default
        sim_sources = sources
        sim_misc = misc
        sim_vcd = waveform_default
    # Valid URL examples: 
    # https://github.com/FPGAOL-CE/user-examples
    # https://github.com/FPGAOL-CE/user-examples/tree/main/tangnano9k

    # Clone a Git URL and compile. No matter the compilation details are specified
    # in this caas_conf or in the repo itself, we always generate a new .caas.conf
    # in the cloned repo specified directory DIR, run caasw mfgen in DIR, and
    # generate a dummy makefile that call make in DIR and copy/move back built
    # results from DIR. 
    if giturl:
        cloneurl, branch, path, reponame = extract_github_url(giturl)
        localdir = os.path.join(proj_dir, reponame)
        # this rel_path is valid in docker, which is important
        target_rel_path = os.path.join(reponame, path)
        target_proj_dir = os.path.join(localdir, path)
        if cloneurl == -1:
            print('Misformed URL: %s, only GitHub URL supported now!' % giturl)
            sys.exit(1)
        print('Git URL specified, repo: %s, branch: %s, path in repo: %s ' % (cloneurl, branch, path))
        if os.path.exists(localdir):
            print('Git repo already exists locally, skip cloning.')
        elif not clone:
            print('Git repo does\'t exist locally, --clone is required for cloning Git URL!')
            sys.exit(1)
        else:
            print('Clone the repo to %s...' % localdir)
            if git_clone(cloneurl, branch, localdir):
                print('Clone failed!')
                sys.exit(1)

        if usegitconf == 'true' or usegitconf == 'True' or usegitconf == '1':
            print('Use specified config(%s) in repo.' % gitconf)
            pass
        else:
            print('Usegitconf not specified, generate .caas.conf for repo...')
            gitconf = '.caas.conf'
            gen_conf = configparser.ConfigParser()
            gen_conf['project'] = {}
            gen_conf['project']['backend'] = backend
            gen_conf['project']['part'] = part
            gen_conf['project']['top'] = top
            gen_conf['project']['sources'] = sources
            gen_conf['project']['constraint'] = constraint
            gen_conf['project']['misc'] = misc
            gen_conf['project']['bitname'] = bitname
            with open(os.path.join(target_proj_dir, gitconf), 'w') as f:
                gen_conf.write(f)
                print('%s writen to %s/' % (gitconf, target_proj_dir))
        # call caasw in target directory for real Makefile gen
        print('Call caas-wizard in %s...' % target_proj_dir)
        # We recommended run caasw in current directory, though in principle
        # specifying any directory will work
        sim_flag = " --sim" if sim else ""
        cmd = "cd " + target_proj_dir + " && " + sys.argv[0] + " --overwrite" + sim_flag + " mfgen ./%s ." % gitconf
        print('------------')
        if os.system(cmd):
            print('Call caas-wizard error!')
            sys.exit(1)
        print('------------')
        # finally, generate dummy script based on mode
        script_name = GENERIC_SIM_SH_NAME if sim else GENERIC_SH_NAME
        print('Write dummy %s...' % script_name)
        os.system('''cat > %s << EOF
#!/bin/sh
curdir=\`pwd\`
cd \$curdir/%s
./%s
ret=\$?
cd \$curdir
mkdir -p %s
cp -rf \$curdir/%s/%s/* \$curdir/%s/
exit \$ret
EOF
''' % (os.path.join(proj_dir, script_name),
     target_rel_path,
     script_name,
     result_dir,
     target_rel_path, result_dir, result_dir))
        os.system('chmod +x %s' % os.path.join(proj_dir, script_name))
        mode_str = "simulation" if sim else "compilation"
        print('Done preperation for Git URL %s.' % mode_str)
        sys.exit(0)

    # We don't need to cover all cases, "bad" cases just return empty

    # deriving family from part name for 7-series
    xc7family = xc7family_derive(part, backend)

    # deriving F4PGA DEVICE from part name
    f4pga_device = f4pga_device_derive(part, backend)
    
    # deriving ecp5 compilation options
    ecp5_part, ecp5_package = ecp5_derive(part, backend)

    # deriving ice40 compilation options
    ice40_part, ice40_package = ice40_derive(part, backend)

    # deriving gowin compilation options
    gowin_part, gowin_family = gowin_derive(part, backend)

    # copy the template files
    print("Copy build files...")
    tools_dir = os.path.join(Path(__file__).parent.absolute(), 'fpga_tools')
    
    # Choose the appropriate Makefile and shell script templates based on simulation mode
    if sim:
        mf_t = os.path.join(tools_dir, 'Makefile.sim')
        sh_t = os.path.join(tools_dir, 'run_sim.sh')
        print("Using simulation mode - copying Makefile.sim and run_sim.sh templates")
    else:
        mf_t = os.path.join(tools_dir, 'Makefile.' + backend)
        sh_t = os.path.join(tools_dir, backend + '.sh')
        print("Using compilation mode - copying Makefile." + backend + " and " + backend + ".sh templates")
    
    mf = os.path.join(proj_dir, makefile)
    sh = os.path.join(proj_dir, script)
    if os.system("cp -v " + mf_t + " " + mf) + \
            os.system("cp -v " + sh_t + " " + sh) != 0:
        print('Error copying Makefile! Backend doesn\'t exist!')
        sys.exit(-1)

    print("Patching build files...")
    # only vivado backend is tcl-based, others are just makefiles
    srcwildcard = ""
    if backend != 'vivado':
        for s in sources.replace("/", "\/").split(","):
            srcwildcard = srcwildcard + " $(wildcard " + s + ") "
    else:
        srcwildcard = sources.replace("/", "\/").replace(",", " ")
    constraintwildcard = ""
    for s in constraint.replace("/", "\/").split(","):
        constraintwildcard = constraintwildcard + " $(wildcard " + s + ") "
    # simulation-specific wildcards
    sim_srcwildcard = ""
    for s in sim_sources.replace("/", "\/").split(","):
        sim_srcwildcard = sim_srcwildcard + " $(wildcard " + s + ") "
    sim_miscwildcard = ""
    for s in sim_misc.replace("/", "\/").split(","):
        sim_miscwildcard = sim_miscwildcard + " $(wildcard " + s + ") "
    os.system(SEDEXEC + " -i " 
              + "-e \'s/__CAAS_TOP/" + top + "/g\' "
              + "-e \'s/__CAAS_SOURCES/" + srcwildcard + "/g\' "
              + "-e \'s/__CAAS_XDC/" + constraintwildcard + "/g\' "
              + "-e \'s/__CAAS_BITNAME/" + bitname + "/g\' "
              + "-e \'s/__CAAS_PART/" + part + "/g\' "
              + "-e \'s/__CAAS_FAMILY/" + xc7family + "/g\' "
              + "-e \'s/__CAAS_F4PGA_DEVICE/" + f4pga_device + "/g\' "
              + "-e \'s/__CAAS_ECP5_PART/" + ecp5_part + "/g\' "
              + "-e \'s/__CAAS_ECP5_PACKAGE/" + ecp5_package + "/g\' "
              + "-e \'s/__CAAS_ICE40_PART/" + ice40_part + "/g\' "
              + "-e \'s/__CAAS_ICE40_PACKAGE/" + ice40_package + "/g\' "
              + "-e \'s/__CAAS_GOWIN_PART/" + gowin_part + "/g\' "
              + "-e \'s/__CAAS_GOWIN_FAMILY/" + gowin_family + "/g\' "
              + "-e \'s/__CAAS_SIM_TOP/" + sim_top + "/g\' "
              + "-e \'s/__CAAS_SIM_SOURCES/" + sim_srcwildcard + "/g\' "
              + "-e \'s/__CAAS_SIM_MISC/" + sim_miscwildcard + "/g\' "
              + "-e \'s/__CAAS_SIM_VCD/" + sim_vcd + "/g\' "
              + mf)

def requestexp(e):
    print("Exception occured when communicating with server: ", e)

# only do upload and query. mfgen, etc are done by server's caasw
def submit(conf_file, proj_dir, dryrun, newjobid):
    import requests
    print(term_white + "Preparing payload for project..." + term_orig)
    caas_conf = configparser.ConfigParser()
    caas_conf.read(conf_file)
    
    # Validate configuration values for special characters
    # This is "frontend", but server will do a validation on the backend nonetheless
    if not validate_config_values(caas_conf):
        print('Configuration input validation failed! Please fix the invalid characters in your configuration file.')
        sys.exit(1)
    
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


def clean(proj_dir):
    for i in [upload_file, download_file, jobid_file, caas_armed_file, GENERIC_MF_NAME, GENERIC_SH_NAME, GENERIC_SIM_SH_NAME, GENERIC_SIM_MF_NAME]:
        try:
            os.remove(os.path.join(proj_dir, i))
        except OSError:
            pass
    print("Temp files cleaned for project ", proj_dir)

if __name__ == '__main__':
    aparse = argparse.ArgumentParser(description='FPGAOL CaaS Wizard')
    aparse.add_argument('op', metavar='OP', type=str, nargs=1, help='Type of operation: mfgen, submit, clean')
    aparse.add_argument('--makefile', action='store', default='DEFAULT', help='mfgen - Name of generated Makefile')
    aparse.add_argument('--script', action='store', default='DEFAULT', help='mfgen - Name of generated compile script')
    aparse.add_argument('--backend', action='store', default=None, help='mfgen - Override backend in caas.conf')
    aparse.add_argument('--overwrite', action='store_const', const=True, default=False, help='mfgen - Overwrite existing files')
    aparse.add_argument('--clone', action='store_const', const=True, default=False, help='clone - specify this with mfgen to get source from Git')
    aparse.add_argument('--dryrun', action='store_const', const=True, default=False, help='submit - Prepare submission files but do not upload')
    aparse.add_argument('--newjobid', action='store_const', const=True, default=False, help='submit - Use a new random jobID')
    aparse.add_argument('--compile', action='store_const', const=True, default=False, help='Run compile')
    aparse.add_argument('--sim', action='store_const', const=True, default=False, help='Run simulation')
    aparse.add_argument('conf', metavar='CONF', type=str, nargs='?', default=caas_conf_default, help='Configuration file (default: %s)' % caas_conf_default)
    aparse.add_argument('dir', metavar='DIR', type=str, nargs='?', default='.', help='Project directory (default: .)')
    args = aparse.parse_args()
    # print(args)
    op = args.op[0]
    conf_file = args.conf
    proj_dir = args.dir
    mfgen_makefile = args.makefile
    mfgen_script = args.script
    mfgen_backend = args.backend
    mfgen_overwrite = args.overwrite
    mfgen_clone = args.clone
    submit_dryrun = args.dryrun
    submit_newjobid = args.newjobid
    mfgen_compile = args.compile
    mfgen_sim = args.sim
    
    # Set correct default makefile name for simulation mode
    if mfgen_makefile == 'DEFAULT':
        mfgen_makefile = GENERIC_SIM_MF_NAME if mfgen_sim else GENERIC_MF_NAME
    if mfgen_script == 'DEFAULT':
        mfgen_script = GENERIC_SIM_SH_NAME if mfgen_sim else GENERIC_SH_NAME
    if op == 'clean':
        clean(proj_dir)
        sys.exit(0)
    if not os.path.isfile(conf_file):
        print('Configuration file %s not found!' % conf_file)
        sys.exit(1)
    if not os.path.exists(proj_dir):
        print('Project directory %s not found!' % proj_dir)
        sys.exit(1)
    if op == 'mfgen':
        mfgen(conf_file, proj_dir, mfgen_makefile, mfgen_script, mfgen_backend, mfgen_overwrite, mfgen_clone, mfgen_sim)
    elif op == 'submit':
        submit(conf_file, proj_dir, submit_dryrun, submit_newjobid)
    else:
        print('Unknown OP:', op)
        sys.exit(1)
    # print(backend, part, top, constraint, sources, family, f4pga_device)
    # print(caas_conf.sections())
