#!/usr/bin/env python

import sys, os, re, argparse, logging, subprocess, csv, inspect
from Bio import SeqIO
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)
import lib.primer as primer
import lib.revcomp_lib as revcomp_lib

class MyFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def __init__(self,prog):
        super(MyFormatter,self).__init__(prog,max_help_position=48)

class col:
    GRN = '\033[92m'
    END = '\033[0m'
    WARN = '\033[93m'


parser=argparse.ArgumentParser(prog='ufits-assign_taxonomy.py', usage="%(prog)s [options] -f <FASTA File>",
    description='''assign taxonomy to OTUs''',
    epilog="""Written by Jon Palmer (2015) nextgenusfs@gmail.com""",
    formatter_class=MyFormatter)

parser.add_argument('-i','--fasta', dest='fasta', required=True, help='FASTA input')
parser.add_argument('-o','--out', dest='out', default='ufits-taxonomy', help='Output file (FASTA)')
parser.add_argument('-m','--method', dest='method', required=True, default='utax',choices=['utax', 'usearch'], help='Taxonomy method')
parser.add_argument('-d','--db', dest='db', help='Reference Database')
parser.add_argument('-u','--usearch', dest="usearch", default='usearch8', help='USEARCH8 EXE')
parser.add_argument('--append_taxonomy', dest="otu_table", nargs='?', help='Append Taxonomy to OTU table')
args=parser.parse_args()

def countfasta(input):
    count = 0
    with open(input, 'rU') as f:
        for line in f:
            if line.startswith (">"):
                count += 1
    return count

def setupLogging(LOGNAME):
    global log
    if 'win32' in sys.platform:
        stdoutformat = logging.Formatter('%(asctime)s: %(message)s', datefmt='%b-%d-%Y %I:%M:%S %p')
    else:
        stdoutformat = logging.Formatter(col.GRN+'%(asctime)s'+col.END+': %(message)s', datefmt='%b-%d-%Y %I:%M:%S %p')
    fileformat = logging.Formatter('%(asctime)s: %(message)s')
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    sth = logging.StreamHandler()
    sth.setLevel(logging.INFO)
    sth.setFormatter(stdoutformat)
    log.addHandler(sth)
    fhnd = logging.FileHandler(LOGNAME)
    fhnd.setLevel(logging.DEBUG)
    fhnd.setFormatter(fileformat)
    log.addHandler(fhnd)

#remove logfile if exists
log_name = args.out + '.log'
if os.path.isfile(log_name):
    os.remove(log_name)

setupLogging(log_name)
FNULL = open(os.devnull, 'w')
cmd_args = " ".join(sys.argv)+'\n'
log.debug(cmd_args)
print "-------------------------------------------------------"

#initialize script, log system info and usearch version
log.info("Operating system: %s" % sys.platform)

if args.method == 'utax':
    if not args.db:
        log.error("No DB specified, exiting")
        os._exit(1)
    usearch = args.usearch
    try:
        usearch_test = subprocess.Popen([usearch, '-version'], stdout=subprocess.PIPE).communicate()[0].rstrip()
    except OSError:
        log.error("%s not found in your PATH, exiting." % usearch)
        os._exit(1)
    version = usearch_test.split(" v")[1]
    majorV = version.split(".")[0]
    minorV = version.split(".")[1]
    if int(majorV) < 8 or (int(majorV) >= 8 and int(minorV) < 1):
        log.warning("USEARCH version: %s detected you need v8.1.1756 or above" % usearch_test)
        os._exit(1)
    else:
        log.info("USEARCH version: %s" % usearch_test)
    
    #Count records
    log.info("Loading FASTA Records")
    total = countfasta(args.fasta)
    log.info('{0:,}'.format(total) + ' OTUs')
    
    #now run through UTAX
    utax_out = args.out + '.utax.txt'
    log.info("Classifying OTUs with UTAX (USEARCH8)")
    log.debug("%s -utax %s -db %s -utaxout %s -utax_cutoff 0.8 -strand both" % (usearch, args.fasta, args.db, utax_out))
    subprocess.call([usearch, '-utax', args.fasta, '-db', args.db, '-utaxout', utax_out, '-utax_cutoff', '0.8', '-strand', 'plus'], stdout = FNULL, stderr = FNULL)
    
    #load results into dictionary for appending to OTU table
    log.debug("Loading results into dictionary")
    with open(utax_out, 'rU') as infile:
        reader = csv.reader(infile, delimiter="\t")
        otuDict = {rows[0]:rows[2] for rows in reader}
    
    
elif args.method == 'usearch':
    if not args.db:
        log.error("No DB specified, exiting")
        os._exit(1)
    usearch = args.usearch
    try:
        usearch_test = subprocess.Popen([usearch, '-version'], stdout=subprocess.PIPE).communicate()[0].rstrip()
    except OSError:
        log.error("%s not found in your PATH, exiting." % usearch)
        os._exit(1)
    log.info("USEARCH version: %s" % usearch_test)
    #Count records
    log.info("Loading FASTA Records")
    total = countfasta(args.fasta)
    log.info('{0:,}'.format(total) + ' OTUs')
    
    #now run through usearch global
    utax_out = args.out + '.usearch.txt'
    log.info("Blasting OTUs with usearch_global")
    log.debug("%s -usearch_global %s -db %s -id 0.7 -top_hit_only -output_no_hits -userout %s -userfields query+target+id -strand both" % (usearch, args.fasta, args.db, utax_out))
    subprocess.call([usearch, '-usearch_global', args.fasta, '-db', args.db, '-userout', utax_out, '-id', '0.7', '-strand', 'both', '-output_no_hits', '-top_hit_only', '-userfields', 'query+target+id'], stdout = FNULL, stderr = FNULL)
    
    #load results into dictionary for appending to OTU table
    log.debug("Loading results into dictionary")
    newTable = []
    with open(utax_out, 'rU') as infile:
        reader = csv.reader(infile, delimiter="\t")
        for line in reader:
            if line[1] == "*":
                newTable.append([line[0], 'No hit'])
            else:
                newTable.append([line[0], re.sub("tax=", "", line[1])+' ('+line[2]+')'])
            
    otuDict = {rows[0]:rows[1] for rows in newTable}
    
log.info("Done classifying OTUs: %s" % utax_out)

if not args.otu_table:
    base = args.fasta.split('otus.fa')[0]
    otu_table = base + 'otu_table.txt'
    if not os.path.exists(otu_table):
        otu_table = base + 'otu_table.csv'
        if not os.path.isfile(otu_table):
            otu_table = ""
        else:
            log.info("Found OTU table: %s" % otu_table)
    else:
        log.info("Found OTU table: %s" % otu_table)

else:
    otu_table = args.otu_table
    
#check if otu_table variable is empty, then load in otu table
if otu_table:
    log.info("Appending taxonomy to OTU table")
    end = otu_table.rsplit(".", 1)[1]
    if end == 'txt':
        d = '\t'
    if end == 'csv':
        d = ','
    basename = otu_table.rsplit(".", 1)[0]
    taxTable = basename + '.taxonomy.txt'
    with open(taxTable, 'w') as outTable:
        with open(otu_table, 'rU') as inTable:
            reader = csv.reader(inTable, delimiter=d)
            for line in reader:
                if 'OTUId' in line[0]:
                    line.append('Taxonomy')
                else:
                    tax = otuDict.get(line[0])
                    line.append(tax)
                join_line = ('\t'.join(str(x) for x in line))
                outTable.write("%s\n" % join_line)
    log.info("Taxonomy finished: %s" % taxTable)
else:
    log.info("Unable to automatically detect OTU table, skipping append taxonomy.  Try to specifiy path to OTU table.")

print "-------------------------------------------------------"