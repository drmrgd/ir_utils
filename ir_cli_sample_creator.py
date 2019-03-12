#!/usr/bin/env python3
# TODO:
#    - Need to add a function to import data from a flat file.  If the DNA and RNA names are
#      not the same, it's tough to figure out how to pair them correctly.  So we have to gen
#      the files and then manually edit them! 
#
# 12/9/2015 - D Sims
###############################################################################################
"""
Generate a 'sample.list' and 'sample.meta' fileset for a group of BAMs to put 
into IR and process.The filenames must be underscore delimited to indicate:


            <sample-(DNA|RNA)>_barcode_runid_ect.bam


The sample name that is used moving forward will be the first element of the BAM
file name, and the last component of that name must be 'DNA' or 'RNA' so that 
the correct nucleic acid type can be input into IR for processing.

We can also use this script to upload VCF files for annotation workflow only. In
this case the naming requirements are far fewer, and no DNA / RNA string is 
required.  

"""
import sys
import os
import re
import argparse
import time
import json
import random
from collections import defaultdict
from termcolor import colored,cprint
from pprint import pprint as pp

version = '4.0.031219'

config_file = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    'config',
    'ir_sample_creator_config.json'
)

class Config(object):
    def __init__(self, config_file):
        self.workflow_data = self.read_config(config_file)

    def __repr__(self):
        return '%s;%s' % (self.__class__, self.__dict__)

    def __getitem__(self, key):
        return self.workflow_data['workflows'][key]

    def __iter__(self,d):
        return self.workflow_data.itervalues()

    def get_workflow(self, name, atype=None):
        '''
        Return a workflow name from the config JSON file to use in 
        sample.meta file.
        '''
        if name == '?':
            self.__print_workflows()
            sys.exit()

        # Validate the analysis type
        try:
            workflow = self.workflow_data[atype][name]
            sys.stdout.write("Using workflow '{}'.\n".format(workflow))
        except KeyError:
            if atype == 'single' and name in self.workflow_data['paired']:
                write_msg(
                    'err', 
                    "Workflow '{}' is a paired DNA + RNA workflow, but a "
                        "'single' analysis type was chosen.".format(name)
                )
            elif atype == 'paired' and name in self.workflow_data['single']:
                write_msg(
                    'err', 
                    "Workflow '{}' is a single DNA, RNA, or VCF workflow, but "
                       "'dna/rna_only' or 'VCF' was not chosen.".format(name)
                )
            else:
                write_msg(
                    "err", '{} is not a valid workflow short name!'.format(name)
                )
            self.__print_workflows()
            sys.exit(1)
        return workflow

    def __validate_type(self, atype):
        if atype not in self.workflow_data.keys():
            write_msg(
                'err', 
                'You have chosen a {} analysis type, but workflow {} is not '
                    'designed for that type of analysis!'.format(atype, 'foo')
            )
            sys.exit()

    def __print_workflows(self):
        for atype in sorted(self.workflow_data):
            sys.stdout.write('%s:\n' % atype)
            for short_name in self.workflow_data[atype]:
                sys.stdout.write("\t{:12}{}\n".format(short_name, 
                    self.workflow_data[atype][short_name]))

    def read_config(self, config_file):
        try:
            with open(config_file) as fh:
                data = json.load(fh)
        except IOError:
            write_msg('err', 'No configuration file found. Do you need to run '
                'the config_gen.py script first?')
            sys.exit(1)
        except ValueError as e:
            sys.stderr.write(
                'ERROR: There is a formatting problem with the JSON config file '
                    '{}: \n{}'.format(config_file, e)
            )
            sys.exit(1)
        return data['workflows']


def get_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'files', 
        nargs="*",
        metavar='<BAM | VCF files>', 
        help='BAM or VCF files to process.'
    )
    parser.add_argument(
        '-d', '--dna_only', 
        action='store_true', 
        help='Samples are DNA only and a DNA only workflow is to be run'
    )
    parser.add_argument(
        '-r', '--rna_only', 
        action='store_true', 
        help='Samples are RNA only and a RNA only workflow is to be run (NOT '
            'YET IMPLEMENTED!)'
    )
    parser.add_argument(
        '-V', '--VCF', 
        action='store_true', 
        help='Upload VCF files rather than BAM files for annotation purposes '
            'only.'
    )
    parser.add_argument(
        '-c', '--cellularity', 
        type=int, 
        choices=range(0, 100), 
        metavar='', 
        default=100, 
        help='Integer value of tumor cellularity to use for the list of samples '
            '(DEFAULT: "%(default)s")'
    )
    parser.add_argument(
        '-t', '--tumor-type', 
        default='Unknown', 
        metavar='', 
        help='Tumor type of each sample indicated need to choose from a '
            'predefined list. (DEFAULT: "%(default)s")'
    )
    parser.add_argument(
        '-g', '--gender', 
        choices=('Male', 'Female', 'Unknown'), 
        default='Unknown', 
        metavar='', 
        help='Gender of sample. Can be "Male", "Female", or "Unknown" (DEFAULT:'
            ' "%(default)s)"'
    )
    parser.add_argument(
        '-w', '--workflow', 
        metavar='', 
        help='IR Workflow to run on all samples. Run with "/?" option to get '
            'list of valid codes.'
    )
    parser.add_argument(
        '--CustomWorkflow',
        metavar='<custom_workflow_name;["paired"|"single"]>',
        help="Custom one-time workflow that is not in the config file. This is "
            "meant to help with single one-off events and is not the preferred "
            "way to input a workflow.  Input the workflow name (using quotes) "
            "exactly as it appears in the IR GUI, followed by either 'paired' "
            "or 'single' to indicate if it's a paired RNA + DNA workflow, or "
            "one of the single workflows.  Note that this is all highly "
            "experimental!"
    )
    parser.add_argument(
        '-v', '--version', 
        action = "version",
        version = '%(prog)s = v' + version
    )
    args = parser.parse_args()

    # Validate selected workflow
    if any(x for x in [args.dna_only, args.rna_only, args.VCF]):
        analysis_type = 'single'
    else:
        analysis_type = 'paired'

    # Get the IR workflow from the config file
    # TODO: Can we bypass this with a workflow name and a type (i.e. "paired
    #       or single)?
    workflows = Config(config_file)
    if args.workflow:
    # XXX: Allow for custom workflow.
        ir_workflow = workflows.get_workflow(args.workflow, analysis_type)
    elif args.CustomWorkflow:
        ir_workflow, analysis_type = args.CustomWorkflow.split(';')
    else:
        write_msg('err', 'You must choose a workflow with either the '
            '`--workflow` or `--CustomWorkflow` options.')
        sys.exit(1)
    if not args.files:
        write_msg(
            'err',
            "You must input at least one BAM / VCF file to be processed!"
        )
        sys.exit(1)

    return args, analysis_type, ir_workflow

def write_msg(flag, string):
    if flag == 'err':
        cprint("ERROR: ", 'red', attrs=['bold'], end='', file=sys.stderr)
    elif flag == 'warn':
        cprint('WARN: ', 'yellow', attrs=['bold'], end='', file=sys.stderr)
    elif flag == 'info':
        cprint('INFO: ', 'cyan', attrs=['bold'], end='', file=sys.stderr)
    sys.stderr.write(string)
    return

def gen_sample_list(sample_data,na_types):
    '''
    Generate the sample.list file that is used with the '-s' option of irucli
    '''
    header = ("# Sample list CSV file for IRUCLI.  Use with the '-s' option.\n# "
        "Sample_Name, Sample_Path, Gender\n")
    outfile = 'sample.list'

    if os.path.isfile(outfile):
        write_msg('warn', "sample.list file already exists! ")
        choice = get_choice('Do you want to overwite:')
        if choice:
            sys.stdout.write("Using new name: {}\n".format(choice))
            outfile = choice
        else:
            sys.stdout.write("Overwriting 'sample.list'...\n")
    sys.stdout.write("Generating a sample list file '{}'...".format(outfile))

    with open(outfile, 'w') as fh:
        fh.write(header)
        for sample in sample_data:
            for i in na_types:
                fh.write('{}-{},{},{}\n'.format(sample, i, sample_data[sample][i], 
                    sample_data[sample]['gender'])
                )
    sys.stdout.write('Done!\n')
    return

def get_choice(query):
    valid_choices = {'y' : 1, 'yes' : 1, 'n' : 2, 'no' : 2, 'rename' : 3, 'r' : 3}
    prompt = ' (y)es, (n)o, (r)ename? '

    while True:
        sys.stdout.write(query + prompt)
        choice = input().lower()
        if choice in valid_choices:
            if valid_choices[choice] == 1:
                return False 
            elif valid_choices[choice] == 2:
                sys.stdout.write("Exiting so that we don't overwrite old data!\n")
                sys.exit(1)
            elif valid_choices[choice] == 3:
                return input("New name: ")
        else:
            sys.stdout.write("Invalid choice '{}'!\n".format(choice))

def gen_sample_meta(sample_data, workflow, na_types):
    '''
    Generate the sample.meta file that is used with the '--customParametersFile'
    option of irucli
    '''
    header = ("# Sample metadata file IRUCLI.  Use with the "
        "'--customParametersFile' option.\n")
    outfile = 'sample.meta'

    if os.path.isfile(outfile):
        write_msg('warn', "sample.meta file already exists! ")
        choice = get_choice('Do you want to overwite:')
        if choice:
            sys.stdout.write("Using new name: {}\n".format(choice))
            outfile = choice
        else:
            sys.stdout.write("Overwriting 'sample.meta'...\n")

    sys.stdout.write("Generating a sample meta file '{}'...".format(outfile))
    with open(outfile, 'w') as fh:
        fh.write(header)
        if len(na_types) > 1: 
            fh.write("_all_samples_=Relation:DNA_RNA,Workflow:{}\n".format(
                workflow))
        else:
            fh.write("_all_samples_=Relation:SINGLE,Workflow:{}\n".format(
                workflow))

        for sample in sample_data:
            setid = "{}_{}".format(int(time.time()), gen_setid())
            cellularity = sample_data[sample]['cellularity']
            gender      = sample_data[sample]['gender']
            tumor       = sample_data[sample]['tumor_type']

            if na_types[0] == 'VCF':
                fh.write('{0}-VCF=RelationRole:{1},cellularityPct:{2},gender:'
                    '{3},cancerType:{4},setid:{5}\n'.format(
                        sample,
                        'SAMPLE',
                        cellularity,
                        gender,
                        tumor,
                        setid
                    )
                )

            else:
                for ntype in na_types:
                    fh.write(
                        "{0}-{1}=NucleotideType:{1},RelationRole:{1},"
                        "cellularityPct:{2},gender:{3},cancerType:{4},"
                        "setid:{5}\n".format(
                            sample,
                            ntype,
                            cellularity,
                            gender,
                            tumor,
                            setid
                        )
                    )
    sys.stdout.write("Done!\n")
    return

def validate_samples(sample_data, na_type):
    '''
    If sample doesn't have both RNA and DNA component, skip it until we have a
    better way to deal with these
    '''
    valid_samples = {}

    for sample in sample_data:
        # Should have 5 keys if both DNA and RNA present; else will be 4 keys. 
        # Shorter than a complex boolean check here I think.
        if len(sample_data[sample]) < 5 and len(na_type) == 2:
            write_msg(
                'warn', 
                "'{}' only has one component but a paired workflow was chosen. "
                    "Need to manually import this sample. Skipping!".format(
                        sample))
            continue
        elif na_type[0] == 'DNA' and 'DNA' not in sample_data[sample]:
            write_msg(
                'warn', 
                "'{}' is a RNA sample, but we require an DNA for this workflow! "
                    "Skipping this sample.".format(sample)
            )
            continue
        elif na_type[0] == 'RNA' and 'RNA' not in sample_data[sample]:
            write_msg(
                'warn', 
                "'{}' is a DNA sample, but we require an RNA for this workflow! "
                    "Skipping this sample.".format(sample)
            )
            continue
        elif na_type[0] == 'VCF' and 'VCF' not in sample_data[sample]:
            write_msg(
                'warn', 
                "'{}' is a VCF sample, and there is a problem with it".format(
                    sample))
            continue
        else:
            valid_samples[sample] = sample_data[sample]

    if len(valid_samples) < 1:
        write_msg('err', 'There are no valid samples to process!\n')
        sys.exit(1)
    return valid_samples

def create_data_table(input_files, datatype, cellularity, gender, tumor_type):
    data = defaultdict(dict)

    if datatype == 'bam':
        for bam in input_files:
            sample, na_type = proc_bams(bam)
            data[sample]['gender']      = gender
            data[sample]['tumor_type']  = tumor_type
            data[sample]['cellularity'] = cellularity
            
            if na_type == 'DNA':
                data[sample]['DNA'] = os.path.abspath(bam)
            else:
                data[sample]['RNA'] = os.path.abspath(bam)
    elif datatype == 'vcf':
        for vcf in input_files:
            sample = vcf.rstrip('.vcf')
            data[sample]['gender'] = gender
            data[sample]['tumor_type'] = tumor_type
            data[sample]['cellularity'] = cellularity
            data[sample]['VCF'] = os.path.abspath(vcf)
    return data

def proc_bams(bam):
    match = re.search(r'^(\w+.*?)[-_](DNA|RNA).*', bam)
    try:
        sample = match.group(1)
        na_type = match.group(2)
    except:
        write_msg(
            'err', 
            "Sample name '{}' is not well formatted! Can't create a sample.list "
            "from this data. Please use format 'sample_name-[DR]NA'.".format(bam)
        )
        sys.exit(1)
    return sample, na_type

def gen_setid():
    return ''.join([random.choice('0123456789abcdef') for x in range(6)])

def main(input_files, dna_only, rna_only, VCF, cellularity, tumor_type, gender,
        analysis_type, ir_workflow):

    # pp(locals())
    # sys.exit()

    datatype = 'bam'
    if dna_only:
        rel_workflow = ['DNA']
    elif rna_only:
        rel_workflow = ['RNA']
    elif VCF:
        datatype = 'vcf'
        rel_workflow = ['VCF']
    else: 
        rel_workflow = ['DNA','RNA']

    sample_table = create_data_table(input_files, datatype, cellularity, gender,
        tumor_type)
    sample_data = validate_samples(sample_table, rel_workflow)

    # Generate the 'sample.list' file
    gen_sample_list(sample_data, rel_workflow)

    # Generate the 'sample.meta' file
    gen_sample_meta(sample_data, ir_workflow, rel_workflow)

if __name__ == '__main__':
    args, analysis_type, ir_workflow = get_args()

    main(args.files, args.dna_only, args.rna_only, args.VCF, args.cellularity,
        args.tumor_type, args.gender, analysis_type, ir_workflow)
