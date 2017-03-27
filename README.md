IR Utils
--
Some common Ion Reporter utilities that make working with upload and download of data much easier. This package
requires the use of a config file to help access the IR API and / or IR Workflows.  Once the packaged is configured
for your system and workflows, this will allow for easy loading of BAM files into IR and processing, along with 
easy retrieval of the variant call ZIP file, and an extraction method to generate a nice working directory tree.

Included in this package are the following utilities:

  * **ir_cli_sample_creator.py**:
    - Starting with a set of BAM files, generate two files needed by the `irucli.sh` utility (the Ion Reporter 
      Commandline Uploader plugin utility) to upload samples, and start and analysis automatically.  

  * **ir_api_retrieve.py**:
    - Starting with a server name, and an analysis ID from IR, retrieve the unfiltered variants ZIP file from
      the IR server.

  * **extract_ir_data.sh**:
    - In a directory containing IR ZIP files that were obtained using `ir_api_retrieve.py`, this script will
      unzip the archive(s) into subdirectories for each analysis, along with copying the vcf files for each
      sample into a 'collected_vcfs' directory for quick and easy access

Each utility (except for `extract_ir_data.sh` will require a configuration file be made in the config directory. This
is the only thing requried to set up this package in fact.  Just descend into `config` and run the `config_gen.py`
script with the appropriate options (generally `--new <config_type> <config_info>`) to set up each IR server connection and IR workflow.  See
the individual `config_gen.py` help docs for more info on how to run this utility.  Once you've set up a config file 
for the two utilities, then just put this whole pacakge into your path, and you're all set to work with IR from the 
commandline.
