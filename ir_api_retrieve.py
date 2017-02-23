#!/usr/bin/python
#
# Python implementation of the ir_apl_retrieve.pl script that doesn't seem to be working due to
# some bugs in the LWP modules.  Re-wrote this to accomodate that as well as deal with SSL 
# issues that seem to be plaguing the perl version of the script across platforms.
#
# 4/1/2015 - D Sims
###############################################################################################
import sys
import os
import argparse
import urllib2
import httplib
import socket
import ssl
import json
from pprint import pprint as pp

version = '2.0.0_022317' 
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
        with open(config_file) as fh:
            data = json.load(fh)
        return data


def get_args():
    parser = argparse.ArgumentParser(
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position=100, width=150),
        description='''
        Starting with a run name from IR or a batch list of run names in a file, grab the filtered and unfiltered variant
        call results from the IR API.  This script also requires an external config file with the API Token in order to access
        the server.
        ''',
        version = '%(prog)s  - ' + version,
        )
    parser.add_argument('host', nargs='?', metavar='<hostname>', help="Hostname of server from which to gather data. Use '?' to print out all valid hosts.")
    parser.add_argument('analysis_id', nargs='?', help='Analysis ID to retrieve if not using a batchfile')
    parser.add_argument('-b','--batch', metavar='<batch_file>', help='Batch file of experiment names to retrieve')
    parser.add_argument('-i', '--ip', metavar='<ip_address>', help='IP address if not entered into the config file yet.')
    parser.add_argument('-t','--token', metavar='<ir_token>', help='API token if not entered into the config file yet.')
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
    filtered_variants_link = metadata[0]['data_links']['filtered_variants']
    unfiltered_variants_link = metadata[0]['data_links']['unfiltered_variants']
    expt_name = metadata[0]['name']

    print "Downloading %s.zip..." % expt_name
    request = urllib2.Request(unfiltered_variants_link,
            headers={'Authorization' : api_token, 'Content-Type' : 'application/x-www-form-urlencoded'}
    )
    try:
        unfiltered_zip = urllib2.urlopen(request)
        with open(expt_name+'_download.zip', 'wb') as zipfile:
            zipfile.write(unfiltered_zip.read())
    except urllib2.HTTPError, error:
        sys.stderr.write('HTTP Error: {}\n'.format(error.read()))
        sys.exit(1)
    except urllib2.URLError, error:
        sys.stderr.write('URL HTTP Error: {}\n'.format(error.read()))
        sys.exit(1)
    return

def connect(self):
    '''Workaround for SSLv3 issue on these servers. Modify the 'connect' function in httplib in order to
    handle SSL better from SO #8039859'''
    sock = socket.create_connection((self.host,self.port),self.timeout,self.source_address)
    if self._tunnel_host:
        self.sock = sock
        self._tunnel()

    self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version = ssl.PROTOCOL_TLSv1)
    return

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
    print json.dumps(json_data, indent=4, sort_keys=True)

def proc_batchfile(batchfile):
    with open(batchfile) as fh:
        return [line.rstrip() for line in fh if line != '\n']

def main():
    cli_args = get_args()
    pp(cli_args)
    program_config = Config.read_config(config_file)
    
    if cli_args.ip and cli_args.token:
        server_url = format_url(cli_args.ip) 
        api_token = cli_args.token
    else:
        server_url,api_token = get_host(cli_args.host,program_config['hosts'])
    print 'host: {}\nip: {}\ntoken: {}'.format(cli_args.host,server_url,api_token)

    analysis_ids=[]
    if cli_args.batch:
        analysis_ids = proc_batchfile(cli_args.batch)
    elif cli_args.analysis_id:
        analysis_ids.append(cli_args.analysis_id)
    else:
        print "ERROR: No analysis ID or batch file loaded!"
        sys.exit(1)

    print('analysis ids:')
    for s in analysis_ids:
        print('\t{}'.format(s))

    api_url = server_url + '/webservices_42/rest/api/analysis?format=json&name='
    httplib.HTTPSConnection.connect=connect

    for expt in analysis_ids:
        print "Getting metadata for " + expt + "..."
        request = urllib2.Request(api_url+expt, 
                headers={'Authorization' : api_token, 'Content-Type' : 'application/x-www-form-urlencoded'}
        )
        try:
            response = urllib2.urlopen(request)
            metadata = json.loads(response.read())
        except urllib2.HTTPError, error:
            sys.stderr.write('HTTP Error: {}\n'.format(error.read()))
            sys.exit(1)
        except urllib2.URLError, error:
            sys.stderr.write('URL HTTP Error: {}\n'.format(error.read()))
            sys.exit(1)

        if metadata:
            download_results(server_url, api_token, metadata)
            print "Done!\n"
        else:
            print "ERROR: No analysis data for '{}'. Check the analysis run name.".format(expt)
            sys.exit(1)

if __name__ == '__main__':
    main()
