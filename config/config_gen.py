#!/usr/bin/python
# Write a config script for package setup to create new config files for IR utils.  We'll need
# to set up individual users' IP addresses, API Tokens, workflows, etc.  
#
# 
###############################################################################################
import sys
import os
import json
import argparse
import datetime
from distutils.version import LooseVersion
from pprint import pprint as pp


version = '0.2.0_032117'

def get_args():
    parser = argparse.ArgumentParser(
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 100, width=200),
        description='''
        <Program Description>
        '''
    )
    parser.add_argument('-n', '--new', choices=('api','sample'), help='Make a new config.json from template. Must choose type to make from list.')
    parser.add_argument('-u', '--update', metavar='<JSON file>', help='Update key / value pair as a comma delimited list (e.g. key,"name of value to update".')
    parser.add_argument('-s', '--server', metavar='hostname:IP_address', 
            help='hostname and IP address, delimited by a colon, for new server to add to the api_retrieve config.')
    parser.add_argument('-w', '--workflow', metavar='short_name:IR_workflow_name', 
            help='short name and IR workflow name (quote names with spaces in them) to be added to the sample_creator config file.')
    parser.add_argument('-j', '--json', metavar='<custom_json_filename>', 
            help='Use custom JSON filename instead of defaults.  WARNING: This might break downstream scripts that rely on the JSON file to have a specific name!')
    parser.add_argument('-v', '--version', action='version', version = '%(prog)s ' + version)
    args = parser.parse_args()

    json_template = args.update
    if args.new == 'api':
        json_template = 'templates/ir_api_retrieve_config.json'
    elif args.new == 'sample':
        json_template = 'templates/ir_sample_creator_config.json'

    new_data = {}
    if args.server:
        new_data['hosts'] = parse_arg(args.server)
    if args.workflow:
        new_data['workflows'] = parse_arg(args.workflow)

    if not args.workflow and not args.server:
        sys.stderr.write('ERROR: you must supply new data for either the api or sample creator config files!.\n')
        sys.exit(1)
        
    if not os.path.exists(json_template):
        sys.stderr.write('ERROR: No such file or directory: %s\n' % json_template)
        sys.exit(1)

    if args.json:
        json_template = args.json

    return json_template, new_data 

def parse_arg(arg):
    return dict(s.split(':') for s in arg.split(','))


class Config(object):
    def __init__(self,config_file):
        self.config_file = config_file
        self.config_data = Config.read_config(self.config_file)
        self.__update_version()

    def __repr__(self):
        return '{}:{}'.format(self.__class__,self.__dict__)

    def __str__(self):
        return pp(dict(self.config_data))

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

    def add_host(self,host,ip):
        return self.config_data['hosts'].update({host : ip})

    def write_config(self,filename=None):
        with open(filename, 'w') as out_fh:
            json.dump(self.config_data,out_fh,indent=4,sort_keys=False)

    def make_blank_template(self,method):
        return
    
    @classmethod
    def read_config(cls,config_file):
        with open(config_file) as fh:
            data = json.load(fh)
        return data

def main():
    json_file,new_data = get_args()
    
    print(json_file)
    print(new_data)
    
    config = Config(json_file)
    print(vars(config))
    sys.exit()
    config.add_host('nci','129.43.127.244')
    config.add_host('drt','129.43.127.192')
    config.add_host('foo','some.invalid.ip')
    config.write_config('test2.json')
    pp(config)

if __name__ == '__main__':
    main()
