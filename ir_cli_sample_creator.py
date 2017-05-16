#!/usr/bin/python
# Utility to generate the files necessary for an IRU CLI upload.
#
# TODO:
#    - Need to add a function to import data from a flat file.  If the DNA and RNA names are
#      not the same, it's tough to figure out how to pair them correctly.  So we have to gen
#      the files and then manually edit them! 
#
#    - Need to strip DNA or RNA from the analysis ID string that is being generated. 
#
# 12/9/2015 - D Sims
###############################################################################################
import sys
import os
import re
import argparse
import time
import json
import random
from collections import defaultdict
from termcolor import colored,cprint
from pprint import pprint

version = '2.5.0_041817'
config_file = os.path.dirname(os.path.realpath(__file__)) + '/config/ir_sample_creator_config.json'

def get_args():
    parser = argparse.ArgumentParser(
        formatter_class = lambda prog: argparse.HelpFormatter(prog, max_help_position = 100, width=200),
        description='''
        Generate a 'sample.list' and 'sample.meta' fileset for a group of BAMs to put into IR and process.
        The filenames should be underscore delimited to indicate:
        
                    <sample-(DNA|RNA)>_barcode_runid_ect.bam

        The sample name that is used moving forward will be the first element of the BAM file name, and 
        the last component of that name must be 'DNA' or 'RNA' so that the correct nucleic acid type can
        be input into IR for processing.

        This is a simple script intended to only upload samples using the same IR Workflow, Cellularity
        Value, Cancer Type, etc.  Eventually we can try to customize this with an input list.
        ''',
        version = '%(prog)s  - ' + version,
        )
    parser.add_argument('bams', nargs='*', metavar='<bamfiles>', help='List of bamfiles to process')
    parser.add_argument('-d', '--dna_only', action='store_true', help='Samples are DNA only and a DNA only workflow is to be run')
    parser.add_argument('-r', '--rna_only', action='store_true', help='Samples are RNA only and a RNA only workflow is to be run (NOT YET IMPLEMENTED!)')
    parser.add_argument('-c', '--cellularity', type=int, choices=xrange(0,100), metavar='INT (0-100)', default=100,
            help='Integer value of tumor cellularity to use for the list of samples (DEFAULT: "%(default)s")')
    parser.add_argument('-t', '--tumor-type', default='Unknown',
            help='Tumor type of each sample indicated need to choose from a predefined list. (DEFAULT: "%(default)s")')
    parser.add_argument('-g', '--gender', choices=('Male', 'Female', 'Unknown'), default='Unknown',
            help='Gender of sample. (DEFAULT: "%(default)s)"')
    parser.add_argument('-w', '--workflow', metavar='STR workflow code', 
            help='IR Workflow to run on all samples.  Must use workflow code (run with "?" option to get list of valid codes), and must use the same for all samples (DEFAULT: "%(default)s").')  
    args = parser.parse_args()

    # Set the workflow type globally here so that we can access later in other functions.
    global DNA_ONLY_WORKFLOW 
    DNA_ONLY_WORKFLOW = args.dna_only 
    global RNA_ONLY_WORKFLOW 
    RNA_ONLY_WORKFLOW = args.rna_only
    
    # Validate selected workflow
    workflows = read_config(config_file)
    ir_workflow = valid_ir_workflows(workflows,args.workflow)

    if len(args.bams) < 2:
        write_msg('err', "You must input at least 1 DNA and 1 RNA BAM file to process!")
        sys.exit(1)
    return args,ir_workflow

def write_msg(flag, string):
    if flag == 'err':
        cprint("ERROR: ", 'red', attrs=['bold'], end='', file=sys.stderr)
    elif flag == 'warn':
        cprint('WARN: ', 'yellow', attrs=['bold'], end='', file=sys.stderr)
    elif flag == 'info':
        cprint('INFO: ', 'cyan', attrs=['bold'], end='', file=sys.stderr)
    print string
    return

def gen_sample_list(sample_data,na_types):
    '''Generate the sample.list file that is used with the '-s' option of irucli'''
    header = "# Sample list CSV file for IRUCLI.  Use with the '-s' option.\n# Sample_Name, Sample_Path, Gender\n"
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
                fh.write('{}-{},{},{}'.format(sample, i, sample_data[sample][i], sample_data[sample]['gender']) + "\n")
    sys.stdout.write('Done!\n')
    return

def get_choice(query):
    valid_choices = {'y' : 1 , 'yes' : 1, 'n' : 2, 'no' : 2, 'rename' : 3, 'r' : 3}
    prompt =  ' (y)es, (n)o, (r)ename? '

    while True:
        sys.stdout.write(query + prompt)
        choice = raw_input().lower()
        if choice in valid_choices:
            if valid_choices[choice] == 1:
                return False 
            elif valid_choices[choice] == 2:
                print "Exiting so that we don't overwrite old data!"
                sys.exit(1)
            elif valid_choices[choice] == 3:
                return raw_input("New name: ")
        else:
            sys.stdout.write("Invalid choice '{}'!\n".format(choice))

def gen_sample_meta(sample_data, workflow, na_types):
    '''Generate the sample.meta file that is used with the '--customParametersFile' option of irucli'''
    header = "# Sample metadata file IRUCLI.  Use with the '--customParametersFile' option.\n"
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
            fh.write("_all_samples_=Relation:DNA_RNA,Workflow:{}\n".format(workflow))
        else:
            fh.write("_all_samples_=Relation:SINGLE,Workflow:{}\n".format(workflow))

        for sample in sample_data:
            setid = "{}_{}".format(int(time.time()), gen_setid())
            for i in na_types:
                fh.write("{}=NucleotideType:{},RelationRole:{},cellularityPct:{},gender:{},cancerType:{},setid:{}\n".format(
                sample +'-'+ i, i, i, sample_data[sample]['cellularity'],sample_data[sample]['gender'],sample_data[sample]['tumor_type'], setid))
    sys.stdout.write("Done!\n")
    return

def valid_ir_workflows(workflows,wf_key):
    '''Generate a workflow name to use in sample.meta file.'''
    single_type_workflows = ('match_dna','pm_blood')
    if not wf_key:
        write_msg('err', "No IR workflow input into script!  You must choose a workflow to run.  Use '-w?' option to see list of valid workflows")
        sys.exit(1)

    if wf_key == '?':
        sys.stdout.write("All valid workflows:\n")
        for key in sorted(workflows):
            sys.stdout.write("\t{:12}{}\n".format(key, workflows[key]))
    elif wf_key in workflows:
        # if (DNA_ONLY_WORKFLOW or RNA_ONLY_WORKFLOW) and not wf_key == 'match_dna':
        if (DNA_ONLY_WORKFLOW or RNA_ONLY_WORKFLOW) and not wf_key in ['match_dna','pm_blood']:
            write_msg('err', 'A DNA or RNA only sample set is being run, but a paired workflow "{}" is selected.  Need to select a DNA or RNA only workflow'.format(wf_key))
            sys.exit(1)

        sys.stdout.write("Using workflow '{}'.\n".format(workflows[wf_key]))
        return workflows[wf_key]
    else:
        write_msg('err', "'{}' is not a valid workflow!\n".format(wf_key))
        valid_ir_workflows('?')
    sys.exit(0)
    return

def validate_samples(sample_data):
    '''If sample doesn't have both RNA and DNA component, skip it until we have a better way to deal with these'''
    valid_samples = {}
    for sample in sample_data:
        # should have 5 keys if both DNA and RNA present; else will be 4 keys.  Shorter than a complex boolean check here I think.
        if len(sample_data[sample]) < 5 and not (DNA_ONLY_WORKFLOW or RNA_ONLY_WORKFLOW):
            write_msg('warn', "'{}' only has one component and can not be paired. Need to manually import this sample. Skipping!".format(sample))
            continue
        else:
            valid_samples[sample] = sample_data[sample]
    return valid_samples

def create_data_table(bams, cellularity, gender, tumor_type):
    data = defaultdict(dict)

    for bam in bams:
        match = re.search(r'^(\w+.*?)[-_](DNA|RNA).*', bam)
        try:
            sample = match.group(1)
            na_type = match.group(2)
        except:
            write_msg('err', "sample name '{}' is not well formatted! Can not create a sample.list file from this data. Please use the format 'sample_name-[DR]NA'.".format(bam))
            sys.exit(1)

        data[sample]['gender']      = gender
        data[sample]['tumor_type']  = tumor_type
        data[sample]['cellularity'] = cellularity

        if na_type == 'DNA':
            data[sample]['DNA'] = os.path.abspath(bam)
        else:
            data[sample]['RNA'] = os.path.abspath(bam)
    data = validate_samples(data)
    return data

def gen_setid():
    return ''.join([random.choice('0123456789abcdef') for x in range(6)])

def read_config(config_file):
    '''Read in a config file of params to use in this program'''
    try:
        with open(config_file) as fh:
            data = json.load(fh)
    except IOError:
        sys.stderr.write("ERROR: No configuration file found. Do you need to run the config_gen.py script first?")
        sys.exit(1)
    workflows = data['workflows']
    return workflows

def main():
    cli_opts, ir_workflow = get_args()
    bams = cli_opts.bams
    sample_data = create_data_table(bams, cli_opts.cellularity, cli_opts.gender, cli_opts.tumor_type)

    # Get sample relationship information (DNA / RNA / DNA-RNA) here and load it into func
    rel_workflow = []
    if DNA_ONLY_WORKFLOW:
        rel_workflow.append('DNA')
    elif RNA_ONLY_WORKFLOW:
        rel_workflow.append('RNA')
    else:
        rel_workflow.extend(['DNA','RNA'])

    # Generate the 'sample.list' file
    gen_sample_list(sample_data,rel_workflow)

    # Generate the 'sample.meta' file
    gen_sample_meta(sample_data,ir_workflow,rel_workflow)

if __name__ == '__main__':
    main()
