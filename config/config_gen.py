#!/usr/bin/python
# Write a config script for package setup to create new config files for IR utils.  We'll need
# to set up individual users' IP addresses, API Tokens, workflows, etc.  
###############################################################################################
import sys
import os
import json
import argparse
import shutil
import datetime
from collections import defaultdict
from termcolor import colored,cprint
from pprint import pprint as pp

version = '1.5.0_051817'


class Config(object):
    def __init__(self,config_file):
        self.config_file = config_file
        self.config_data = Config.read_config(self.config_file)
        self.__update_version()

    def __repr__(self):
        return '{}:{}'.format(self.__class__,self.__dict__)

    def __str__(self):
        return str(pp(self.config_data))

    def __getitem__(self,key):
        return self.config_data[key]

    def __iter__(self):
        return self.config_data.itervalues()

    def __update_version(self):
        '''Automatically increment the version string'''
        v,d = self.config_data['version'].split('.')
        today = str(datetime.datetime.now().strftime('%m%d%y'))
        return self.config_data.update({'version' : '{}.{}'.format(str(int(v)+1),today)})

    def add_workflow(self,data):
        '''Add workflow shortname and IR matching name to config file.  Requires a dict of workflow data in the form:
                {<single|paired> : {<short_name> : <ir_name>}}
           Since we're using a dict.update() method, can also use same function for updating the 
           config file.
        '''
        return self.config_data['workflows'].update(data)

    def add_host(self,data):
        '''Add host, ip, and token to config file.  Requires a dict of host data in the form:
                {<hostname> : { 'ip' : <ip_address>, 'token' : <api_token>}}
           Since we're using a dict.update() method, can also use same function for updating the 
           config file.
        '''
        return self.config_data['hosts'].update(data)

    def write_config(self,filename=None):
        '''Write the config file out to disk. Have left room for custom naming, though this is not
        preferred as the utils are specifically looking for a certain filename.
        '''
        if filename:
            json_out = filename
        else: 
            json_out = self.config_file
        with open(json_out, 'w') as out_fh:
            json.dump(self.config_data,out_fh,indent=4,sort_keys=False)

    def __make_blank_template(self,method):
        '''Make a brand new shiny template file to use for something else. Not yet needed, but can
        add later.
        '''
        return
    
    @classmethod
    def read_config(cls,config_file):
        with open(config_file) as fh:
            data = json.load(fh)
        return data


def get_args():
    parser = argparse.ArgumentParser(
        formatter_class = lambda prog: argparse.HelpFormatter(prog, width=125),
        description='''
        Configuration file generation utility for ir_utils.  Needed to make a IR API Retrieve and IR CLI Sample Creator
        config files with credential and server information.  Can be used to generate a new, fresh config file, or to
        update an existing config file.  Return will be a new config file for the IR Utils package, along with a backup
        of the last config file if one existed.
        '''
    )
    parser.add_argument('-m', '--method', choices=('api','sample'), required=True,
            help='Type of config file to be made or updated.')
    parser.add_argument('-u', '--update', action='store_true',
            help='''Update a config file with new data. Must use either the "server" and "token" options for an 
                    API config, or the 'workflow' and 'analysis_type' options for a sample uploader config''')
    
    parser.add_argument('-s', '--server', metavar='<hostname:IP_address>', 
            help='Hostname and IP address, delimited by a colon, for new server to add to the api_retrieve config.')
    parser.add_argument('-t', '--token', metavar='<api_token>', 
            help='API Token used for IR API Retrieve. This can be determined from a user account on the IR server to be added..')

    parser.add_argument('-w', '--workflow', metavar='short_name:IR_workflow_name', 
            help='''Short name and IR workflow name (quote names with spaces in them), delimited by a colon, to be added 
                    to the sample_creator config file. The full workflow name must match exactly the name that's indicated
                    in the IR GUI.''')
    parser.add_argument('-a', '--analysis_type', choices=('single','paired'),
            help='Indicate if the workflow is for a paired DNA / RNA or a single RNA / single DNA specimen.')

    parser.add_argument('-f', '--file', metavar='<file>', 
            help='''Read config data from a flat CSV file rather than inputting each element on the commandline. Each line of the file should
                    be formatted similarly to the way data would normally be entered (e.g short_name:IR_name,single or host:ip,token). This 
                    method will be helpful for instances where we need to add a lot of stuff to one config.''')

    parser.add_argument('--version', action='version', version = '%(prog)s ' + version)
    args = parser.parse_args()

    new_data = defaultdict(dict)

    # Get and check the passed args to set up data struct for updating the file.
    if args.file:
        '''process the file accordingly'''
        print('Getting params from a flat file: %s' % (args.file))
        validate_file(args.file,args.method)
        new_data = read_flat_file(args.file,args.method)
    else:
        if args.method == 'sample':
            if not all((args.workflow,args.analysis_type)):
                write_msg('err','Missing data! You must indicate the workflow name and if the new workflow is a "paired" or "single" workflow when using the "sample" method!\n\n')
                parser.print_help()
                sys.exit(1)
            else:
                short_name,workflow = args.workflow.split(':')
                new_data[args.analysis_type][short_name] = workflow
        elif args.method == 'api':
            if not all((args.server,args.token)):
                write_msg('err','Missing data! You must indicate the server name and input an API token when using the API method.\n\n')
                parser.print_help()
                sys.exit(1)
            else:
                host,ip = args.server.split(':')
                if not ip.startswith('https://'):
                    ip = 'https://' + ip
                new_data[host] = {
                    'ip' : ip,
                    'token' : args.token
                }

    # Choose which template we're working with and check to be sure it's the right one
    if args.update:
        if args.method == 'api':
            json_template = 'ir_api_retrieve_config.json'
        else:
            json_template = 'ir_sample_creator_config.json'
    elif args.method == 'api':
        json_template = 'templates/ir_api_retrieve_config.tmplt'
    elif args.method == 'sample':
        json_template = 'templates/ir_sample_creator_config.tmplt'

    return args.method, json_template, new_data, args.update


def validate_file(flatfile,method):
    with open(flatfile) as fh:
        for line_num, line in enumerate(fh):
            terminal_string = line.rstrip('\n').split(',')[1]
            if method == 'sample' and terminal_string not in ('single','paired'):
                sys.stderr.write('ERROR: Invalid string "{}" in following line of input file (expected only "single" or "paired"):\n'.format(terminal_string))
                sys.stderr.write('{}: {}\n'.format(line_num,line))
                sys.exit(1)
            elif method == 'api' and terminal_string in ('single', 'paired'):
                sys.stderr.write('ERROR: Invalid string "{}" in following line of input file (expected an API token):\n'.format(terminal_string))
                sys.stderr.write('{}: {}\n'.format(line_num,line))
                sys.exit(1)

def read_flat_file(f,method):
    parsed_data = defaultdict(dict)
    with open(f) as fh:
        for line in fh:
            elems = line.rstrip('\n').split(',')
            if method == 'sample':
                sname, lname = elems[0].split(':')
                parsed_data[elems[1]].update({sname:lname})
            elif method == 'api':
                host,ip = elems[0].split(':')
                parsed_data[host].update({"ip": ip, "token":elems[1]})

    pp(dict(parsed_data))
    sys.exit()
    return

def write_msg(flag, string):
    if flag == 'err':
        cprint("ERROR: ", 'red', attrs=['bold'], end='', file=sys.stderr)
    elif flag == 'warn':
        cprint('WARN: ', 'yellow', attrs=['bold'], end='', file=sys.stderr)
    elif flag == 'info':
        cprint('INFO: ', 'cyan', attrs=['bold'], end='', file=sys.stderr)
    print(string)
    return

def edit_config(json_file,config_type,new_data):
    config = Config(json_file)
    if config_type == 'api':
        config.add_host(new_data)
    elif config_type == 'sample':
        config.add_workflow(new_data)
    config.write_config()
    return

def backup_config(jfile):
    shutil.copy(jfile,jfile+'~')

def main():
    method,source_json_file,new_data,update = get_args()
    debug = True
    if debug:
        print('{}  DEBUG  {}'.format('-'*30, '-'*30))
        print('method: {}\nsource_json_file: {}\nupdate: {}'.format(method, source_json_file, update))
        pp(dict(new_data))
        print('-'*69)

    if update:
        '''backup the current config file and edit'''
        print('Updating {}.'.format(source_json_file))
        backup_config(source_json_file)
        edit_config(source_json_file,method,new_data)
    else: 
        new_json = os.path.join(os.getcwd(),os.path.basename(source_json_file).replace('tmplt','json'))
        print('Making a new JSON file: {}'.format(new_json))
        if os.path.exists(new_json):
            backup_config(new_json)
        shutil.copy(source_json_file,new_json)
        edit_config(new_json,method,new_data)

if __name__ == '__main__':
    main()
