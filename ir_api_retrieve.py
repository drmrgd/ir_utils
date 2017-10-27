#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# 4/1/2015 - D Sims
###############################################################################################
"""
Starting with a run name from IR or a batch list of run names in a file, grab the filtered and unfiltered variant
call results from the IR API.  This script also requires an external config file with the API Token in order to access
the server.
"""
import sys
import os
import argparse
import json
import requests
import zipfile
import datetime
from termcolor import colored,cprint
from pprint import pprint as pp

version = '4.0.0_102717' 
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
        description = __doc__,
    )
    parser.add_argument('host', nargs='?', metavar='<hostname>', 
        help="Hostname of server from which to gather data. Use '?' to print out all valid hosts.")
    parser.add_argument('analysis_id', nargs='?', 
        help='Analysis ID to retrieve if not using a batchfile')
    parser.add_argument('-b','--batch', metavar='<batch_file>',
        help='Batch file of experiment names to retrieve')
    parser.add_argument('-i', '--ip', metavar='<ip_address>',
        help='IP address if not entered into the config file yet.')
    parser.add_argument('-t','--token', metavar='<ir_token>',
        help='API token if not entered into the config file yet.')
    parser.add_argument('-m','--method', metavar='<api_method_call>', 
        help='Method call / entry point to API. ****  Not yet implemented  ****')
    parser.add_argument('-d', '--date_range', metavar='<YYYY-MM-dd,YYYY-MM-dd>', 
        help='Range of dates in the format of "start,end" where each date is in the format '
            'YYYY-MM-dd. This will be the range which will be used to pull out results. One '
            'can input only 1 date if the range is only going to be one day.')
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

    if cli_args.date_range:
        start,end = cli_args.date_range.split(',')
        __validate_date(start)
        __validate_date(end)

    return cli_args

def __validate_date(date):
    try:
        datetime.datetime.strptime(date, '%Y-%M-%d')
    except ValueError:
        sys.stderr.write("ERROR: the date '%s' is not in a valid format.  You must use YYYY-MM-dd.\n")
        sys.exit(1)

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

def api_call(url, query, header, batch_type, name=None):
    requests.packages.urllib3.disable_warnings()
    s = requests.Session()
    request = s.get(url,headers=header,params=query,verify=False)
    try:
        request.raise_for_status()
    except requests.exceptions.HTTPError as error:
        cprint('\n\n\t{}'.format(error), 'red', attrs=['bold'], file=sys.stderr)
        if batch_type == 'range':
            cprint('\tThere may be no data available for the range input. Check the date range and try again.\n','red', attrs=['bold'], file=sys.stderr)
        else:
            cprint('\tSkipping analysis id: {}. Check ID for this run and try again.\n'.format(query['name']), 'red', attrs=['bold'], file=sys.stderr)
        return None

    json_data = request.json()
    num_sets = len(json_data)
    count = 0

    if batch_type == 'range':
        sys.stdout.write('Done!\n')
        sys.stdout.write('Total number to retrieve: %s.\n' % num_sets)
        sys.stdout.flush()

    for analysis_set in json_data:
        data_link = analysis_set['data_links']
        if batch_type == 'range':
            count += 1
            name = analysis_set['name']
            sys.stdout.write('  [{}/{}] Retrieving VCF data for analysis ID: {}...'.format(count, num_sets, name))
            sys.stdout.flush()
        zip_name = name + '_download.zip'

        with open(zip_name, 'wb') as zip_fh:
            response = s.get(data_link, headers=header, verify=False)
            zip_fh.write(response.content)

        print('Done!')

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
    elif not cli_args.date_range:
        print("ERROR: No analysis ID or batch file loaded!")
        sys.exit(1)

    header = {'Authorization':api_token,'content-type':'application/x-www-form-urlencoded'}
    method='getvcf'
    url = server_url + method

    if cli_args.date_range:
        start,end = cli_args.date_range.split(',')
        sys.stdout.write('Getting list of results from IR {} for dates from {} to {}...'.format(cli_args.host, start, end))
        sys.stdout.flush()
        query = {'format' : 'json', 'start_date' : start, 'end_date' : end, 'exclude' : 'filteredvariants' }
        api_call(url, query, header, 'range')
    else:
        sys.stdout.write('Getting data from IR {} (total runs: {}).\n'.format(cli_args.host,len(analysis_ids)))
        sys.stdout.flush()
        count = 0
        for expt in analysis_ids:
            count += 1
            sys.stdout.write('  [{}/{}]  Retrieving VCF data for analysis ID: {}...'.format(
                count, len(analysis_ids), expt)
            )
            sys.stdout.flush()
            query = {'format' : 'json', 'name' : expt, 'exclude' : 'filteredvariants'}
            api_call(url, query, header, 'single', expt)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
