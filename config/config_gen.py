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

version = '0.6.0_032117'

def get_args():
    parser = argparse.ArgumentParser(
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 100, width=150),
        description='''
        Configuration file generation utility for ir_utils.  Needed to make a IR API Retrieve and IR CLI Sample Creator
        config files with credential and server information.  Can be used to generate a new, fresh config file, or to
        update an existing config file.
        '''
    )
    parser.add_argument('--new', choices=('api','sample'),
            help='Make a new config.json from template. Must choose type to make from list.')

    parser.add_argument('--update', metavar='<JSON file>', help='Update key / value pair as a comma delimited list (e.g. key,"name of value to update".')

    parser.add_argument('--server', metavar='hostname:IP_address', 
            help='Hostname and IP address, delimited by a colon, for new server to add to the api_retrieve config.')
    parser.add_argument('--token', metavar='<api_token>', 
            help='API Token used for IR API Retrieve.  Must be input for new IR connections.')

    parser.add_argument('--workflow', metavar='short_name:IR_workflow_name', 
            help='Short name and IR workflow name (quote names with spaces in them), delimited by a colon, to be added to the sample_creator config file.')

    parser.add_argument('--version', action='version', version = '%(prog)s ' + version)
    args = parser.parse_args()
    print('args list:\n{}\n'.format(vars(args)))

    # Determine method (new or update) and make sure we have the right args.
    method = ''
    if args.new:
        method = 'new'
    else:
        method = 'update'

    if not any((args.new, args.update)):
        write_msg('err', "You must choose to either create a new JSON or update an existing one!\n\n")
        print(parser.print_help())
        sys.exit(1)
    elif not args.workflow and not all((args.server,args.token)):
        write_msg('err','Missing data! You must supply new data for either the api or sample creator config files!.\n\n')
        print(parser.print_help())
        sys.exit(1)
    
    # Choose which template we're working with.
    json_template = args.update
    if args.new == 'api':
        json_template = 'templates/ir_api_retrieve_config.tmplt'
    elif args.new == 'sample':
        json_template = 'templates/ir_sample_creator_config.tmplt'

    type_flag = os.path.basename(json_template).split('_')[1]
    if type_flag == 'api' and args.workflow:
        write_msg('err','Mismatch between args (--workflow) and config type (--api)!\n\n')
        print(parser.print_help())
        sys.exit(1)
    elif type_flag == 'sample' and args.server:
        write_msg('err','Mismatch between args (--server) and config type (--sample)!\n\n')
        print(parser.print_help())
        sys.exit(1)
    
    # Set up dict of new data to process
    new_data = defaultdict(dict)
    if args.server:
        if not args.token:
            write_msg('err','You must input a token for the new server using the --token opt')
            print(parser.print_help())
            sys.exit(1)
        host,ip = args.server.split(':')
        # new_data['hosts'][host] = {
        new_data[host] = {
            'ip' : ip,
            'token' : args.token
        }
    elif args.workflow:
        short_name,workflow = args.workflow.split(':')
        new_data['workflows'][short_name] = workflow

    print("new data: ")
    pp(dict(new_data))
    print('')

    # TODO:  Should probably output new or update so that we can do some file backing up adn stuff.
    return method, json_template, new_data, type_flag

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

    def add_workflow(self,workflow_id,workflow_name):
        return self.config_data['workflows'].update({workflow_id: workflow_name})

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
    print('config obj:\n{}\n'.format(vars(config)))
    if config_type == 'api':
        config.add_host(new_data)
        config.write_config()
        # config.old_add_host('test','123.456.789.900')
        print(config)
    return

def backup_config(jfile):
    shutil.copy(jfile,jfile+'~')

def main():
    method,source_json_file,new_data,config_type = get_args()

    # If we're making a new config file, copy a blank from templates and edit into this dir.  
    # If we just want to update the current config file, then make a backup and then edit.
    if method == 'new':
        new_json = os.path.join(os.getcwd(),os.path.basename(source_json_file).replace('tmplt','json'))
        if os.path.exists(new_json):
            backup_config(new_json)
        shutil.copy(source_json_file,new_json)
        edit_config(new_json,config_type,new_data)
    else:
        '''backup the current config file and edit'''
        backup_config(source_json_file)
        edit_config(source_json_file,config_type,new_data)
    sys.exit()

    config.add_host('nci','129.43.127.244')
    config.add_host('drt','129.43.127.192')
    config.add_host('foo','some.invalid.ip')
    config.write_config('test2.json')
    pp(config)

if __name__ == '__main__':
    main()
