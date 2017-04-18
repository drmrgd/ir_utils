#!/usr/bin/python
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
# import urllib2
# import httplib
# import socket
# import ssl
import json
import requests
import zipfile
from pprint import pprint as pp

version = '2.1.1_032717' 
config_file = os.path.dirname(os.path.realpath(__file__)) + '/config/ir_api_retrieve_config.json'

DEBUG = False


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

def download_results(server_url,api_token,metadata):
    '''TODO: Deprecated. To be removed'''
    filtered_variants_link = metadata[0]['data_links']['filtered_variants']
    unfiltered_variants_link = metadata[0]['data_links']['unfiltered_variants']
    expt_name = metadata[0]['name']

    print("Downloading %s.zip..." % expt_name)
    request = urllib2.Request(unfiltered_variants_link,
            headers={'Authorization' : api_token, 'Content-Type' : 'application/x-www-form-urlencoded'}
    )
    try:
        unfiltered_zip = urllib2.urlopen(request)
        with open(expt_name+'_download.zip', 'wb') as zipfile:
            zipfile.write(unfiltered_zip.read())
    except urllib2.HTTPError as error:
        sys.stderr.write('HTTP Error: {}\n'.format(error.read()))
        sys.exit(1)
    except urllib2.URLError as error:
        sys.stderr.write('URL HTTP Error: {}\n'.format(error.read()))
        sys.exit(1)
    return

# TODO: remove this.
# def connect(self):
    # '''Workaround for SSLv3 issue on these servers. Modify the 'connect' function in httplib in order to
    # handle SSL better from SO #8039859'''
    # sock = socket.create_connection((self.host,self.port),self.timeout,self.source_address)
    # if self._tunnel_host:
        # self.sock = sock
        # self._tunnel()

    # self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version = ssl.PROTOCOL_TLSv1)
    # return

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
        sys.stderr.write('{}\n'.format(error))
        sys.exit(1)
    json_data = request.json()
    # jdump(json_data)
    # sys.exit()
    data_link = json_data[0]['data_links']
    if 'unfiltered_variants' in data_link:
        zip_path = data_link['unfiltered_variants']
    else:
        zip_path = data_link
    zip_name = name + '_download.zip'
    with open(zip_name, 'wb') as zip_fh:
        # response = s.get(data_link,headers=header,verify=False)
        response = s.get(zip_path,headers=header,verify=False)
        zip_fh.write(response.content)
    return

def main():
    cli_args = get_args()
    if DEBUG:
        pp(cli_args)
    program_config = Config.read_config(config_file)
    
    if cli_args.ip and cli_args.token:
        server_url = format_url(cli_args.ip) 
        api_token = cli_args.token
    else:
        server_url,api_token = get_host(cli_args.host,program_config['hosts'])
    server_url += '/api/v1/'
    if DEBUG:
        print('host: {}\nip: {}\ntoken: {}'.format(cli_args.host,server_url,api_token))

    analysis_ids=[]
    if cli_args.batch:
        analysis_ids = proc_batchfile(cli_args.batch)
    elif cli_args.analysis_id:
        analysis_ids.append(cli_args.analysis_id)
    else:
        print("ERROR: No analysis ID or batch file loaded!")
        sys.exit(1)

    if DEBUG:
        print('analysis ids:')
        for s in analysis_ids:
            print('\t{}'.format(s))

    # api_url = server_url + '/webservices_42/rest/api/analysis?format=json&name='
    # httplib.HTTPSConnection.connect=connect

    new_test = True 
    # TODO:  Add a nice counter and output here.
    for expt in analysis_ids:
        if new_test:
            use_new_method(server_url,expt,api_token)
            continue

        print("Getting metadata for " + expt + "...")
        request = urllib2.Request(api_url+expt, 
                headers={'Authorization' : api_token, 'Content-Type' : 'application/x-www-form-urlencoded'}
        )
        try:
            response = urllib2.urlopen(request)
            metadata = json.loads(response.read())
        except urllib2.HTTPError as error:
            sys.stderr.write('HTTP Error: {}\n'.format(error.read()))
            sys.exit(1)
        except urllib2.URLError as error:
            sys.stderr.write('URL HTTP Error: {}\n'.format(error.read()))
            sys.exit(1)

        if metadata:
            if DEBUG : jdump(metadata)
            download_results(server_url, api_token, metadata)
            print("Done!\n")
        else:
            print("ERROR: No analysis data for '{}'. Check the analysis run name.".format(expt))
            sys.exit(1)

def use_new_method(server_url,expt,api_token,method='getvcf'):
    '''Quickie wrapper to get new data out as I'm testing a couple methods.  Will merge this wil main()'''
    sys.stdout.write('Retrieving VCF data for analysis ID: {}...'.format(expt))
    sys.stdout.flush()
    header = {'Authorization':api_token,'content-type':'application/x-www-form-urlencoded'}
    query = {'format':'json','name':expt}
    url = server_url + method
    api_call(url,query,header,expt)
    print('Done!')

if __name__ == '__main__':
    main()
