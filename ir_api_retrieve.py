#!/usr/bin/env python3
# Retrieve VCF data from an Ion Reporter Server based on run id.  Requires a config file that 
# has information about the server from which we'll get data, as well as, the API token used
# to access the IR API.  
#
# TODO: Completely re-written for speed!
#       - Can we add some other method calls to the API now that we have requests generate 
#         the query for us?
#       - No longer get all settings and QC metrics, which not often used. maybe this is 
#         good method for new method calls?
#
# 4/1/2015 - D Sims
###############################################################################################
import sys
import os
import argparse
import json
import requests
import zipfile
from termcolor import colored,cprint
from pprint import pprint as pp

version = '3.0.0_041817' 
config_file = os.path.dirname(os.path.realpath(__file__)) + '/config/ir_api_retrieve_config.json'


class Config(object):
    def __init__(self,config_file):
        self.config_file = config_file
        self.config_data = Config.read_config(self.config_file)

    def __repr__(self):
        return '%s:%s' % (self.__class__,self.__dict__)

    def __getitem__(self,key):
        return self.config_data[key]

    def __iter__(self):
        return self.config_data.itervalues()

    @classmethod
    def read_config(cls,config_file):
        '''Read in a config file of params to use in this program'''
        try:
            with open(config_file) as fh:
                data = json.load(fh)
        except IOError:
            sys.stderr.write("ERROR: No configuration file found. Do you need to run the config_gen.py script first?\n")
            sys.exit(1)
        return data


def get_args():
    parser = argparse.ArgumentParser(
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position=100, width=150),
        description='''
        Starting with a run name from IR or a batch list of run names in a file, grab the filtered and unfiltered variant
        call results from the IR API.  This script also requires an external config file with the API Token in order to access
        the server.
        ''',
        )
    parser.add_argument('host', nargs='?', metavar='<hostname>', help="Hostname of server from which to gather data. Use '?' to print out all valid hosts.")
    parser.add_argument('analysis_id', nargs='?', help='Analysis ID to retrieve if not using a batchfile')
    parser.add_argument('-b','--batch', metavar='<batch_file>', help='Batch file of experiment names to retrieve')
    parser.add_argument('-i', '--ip', metavar='<ip_address>', help='IP address if not entered into the config file yet.')
    parser.add_argument('-t','--token', metavar='<ir_token>', help='API token if not entered into the config file yet.')
    parser.add_argument('-m','--method', metavar='<api_method_call>', 
            help='Method call / entry point to API. ****  Not yet implemented  ****')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + version)
    cli_args = parser.parse_args()

    if not cli_args.host:
        if cli_args.ip and not cli_args.token:
            sys.stderr.write("ERROR: You must enter a custom token with the '-t' option if you are using a custom IP.\n")
            sys.exit(1)
        elif cli_args.token and not cli_args.ip:
            sys.stderr.write("ERROR: You must enter an IP with the '-i' option if you are using a custom token.\n")
            sys.exit(1)
        elif not cli_args.ip and not cli_args.token:
            sys.stderr.write("ERROR: You must either enter a host name or a custom IP and token!\n")
            sys.exit(1)

    return cli_args

def get_host(hostname,hostdata=None):
    '''Return the IP address and API token of the server from which we wish to retrieve data'''

    if hostname == '?':
        print("Current list of valid list of hosts are: ")
        for host in hostdata:
            print("\t{}".format(host))
        sys.exit()
    else:
        try:
            ip = hostdata[hostname]['ip']
            token = hostdata[hostname]['token']
        except KeyError:
            sys.stderr.write("ERROR: '{}' is not a valid IR Server name.\n".format(hostname))
            get_host('?',hostdata)
            sys.exit(1)
    return ip, token

def format_url(ip):
    pieces = ip.lstrip('https://').split('.')
    if len(pieces) != 4: 
        sys.stderr.write("ERROR: the IP address you entered, '{}', does not appear to be valid!\n".format(ip))
        sys.exit(1)
    if all(0<=int(p)<256 for p in pieces):
        return 'https://{}'.format('.'.join(pieces))
    else:
        sys.stderr.write("ERROR: the IP address you entered, '{}', does not appear to be valid!\n".format(ip))
        sys.exit(1)

def jdump(json_data):
    print(json.dumps(json_data, indent=4, sort_keys=True))

def proc_batchfile(batchfile):
    with open(batchfile) as fh:
        return [line.rstrip() for line in fh if line != '\n']

def api_call(url,query,header,name):
    requests.packages.urllib3.disable_warnings()
    s = requests.Session()
    request = s.get(url,headers=header,params=query,verify=False)
    try:
        request.raise_for_status()
    except requests.exceptions.HTTPError as error:
        cprint('\n\n\t{}'.format(error), 'red', attrs=['bold'], file=sys.stderr)
        cprint('\tSkipping analysis id: {}. Check ID for this run and try again.\n'.format(query['name']), 'red', attrs=['bold'], file=sys.stderr)
        return None

    json_data = request.json()
    data_link = json_data[0]['data_links']
    if 'unfiltered_variants' in data_link:
        zip_path = data_link['unfiltered_variants']
    else:
        zip_path = data_link

    zip_name = name + '_download.zip'
    with open(zip_name, 'wb') as zip_fh:
        response = s.get(zip_path,headers=header,verify=False)
        zip_fh.write(response.content)
    print('Done!')
    return

def main():
    cli_args = get_args()
    program_config = Config.read_config(config_file)
    
    if cli_args.ip and cli_args.token:
        server_url = format_url(cli_args.ip) 
        api_token = cli_args.token
    else:
        server_url,api_token = get_host(cli_args.host,program_config['hosts'])
    server_url += '/api/v1/'

    analysis_ids=[]
    if cli_args.batch:
        analysis_ids = proc_batchfile(cli_args.batch)
    elif cli_args.analysis_id:
        analysis_ids.append(cli_args.analysis_id)
    else:
        print("ERROR: No analysis ID or batch file loaded!")
        sys.exit(1)

    header = {'Authorization':api_token,'content-type':'application/x-www-form-urlencoded'}
    method='getvcf'
    url = server_url + method

    sys.stdout.write('Getting data from IR {} (total runs: {}).\n'.format(cli_args.host,len(analysis_ids)))
    count = 0
    for expt in analysis_ids:
        count += 1
        sys.stdout.write('  [{}/{}]  Retrieving VCF data for analysis ID: {}...'.format(count,len(analysis_ids),expt))
        sys.stdout.flush()
        query = {'format':'json','name':expt}
        api_call(url,query,header,expt)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
