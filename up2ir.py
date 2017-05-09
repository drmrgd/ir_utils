#!/usr/bin/env python3
# Try to generate a wrapper script for irucli so that we can do this a little easier. 
# 
# 4/17/2017 - D Sims
##################################################################################################################
import sys
import os
import subprocess
from getpass import getpass

version='1.0.041717'
irucli_path = os.environ['HOME'] + '/Dropbox/ir_stuff/IonReporterUploader-cli_5.2.0.66'

def get_config(site):
    base_path = os.path.join(irucli_path,'config_files/')
    sites = ['mocha_ir', 'nci_ir', 'mgh_ir', 'drt_ir', 'mda_ir', 'ysm_ir']
    if site == '?':
        print('Valid sites are:')
        for site in sites:
            print('  {}'.format(site))
    else:
        if site in sites:
            return base_path + site + '.cfg'
        else:
            sys.stderr.write("ERROR: '{}' is not a valid site!\n".format(site))
            sys.stderr.flush()
            get_config('?')
            sys.exit(1)

def upload_to_ir(config,password):
    irucli_exec = os.path.join(irucli_path, 'bin/irucli.sh')
    cmd = [irucli_exec, '-c', config, '-l', 'log', '-s', 'sample.list', '--customParametersFile', 'sample.meta']

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, bufsize=1)
    p.stdin.write(str.encode(password+os.linesep))
    p.stdin.flush()
    while p.poll() is None:
        out = p.stdout.readline()
        sys.stdout.write(out.decode('utf-8'))
        sys.stdout.flush()

def usage():
    sys.stdout.write("USAGE: {} <ir_name>\n".format(os.path.basename(__file__)))
    sys.stdout.write("\nOptions:\n\t ?\tList of valid IR Servers\n\t-h\tThis help text\n")
    sys.exit()

if __name__=='__main__':
    try:
        site = sys.argv[1]
    except IndexError:
        sys.stderr.write("ERROR: You must enter the IR site name to which we'll upload data!\n")
        usage()
        sys.exit(1)

    if site == '-h':
        usage()
        sys.exit(1)
    elif site == '?':
        get_config('?')
        sys.exit()
    else:
        config = get_config(site)
        if not os.path.exists(config):
            sys.stderr.write("ERROR: Can not find config file: {}\n".format(config))
            sys.exit(1)

    password = getpass('Enter password for {}: '.format(site))
    upload_to_ir(config,password)
