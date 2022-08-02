#!/bin/sh
# Create top-level RECORDS file based on folders
# Should be "RECORDS_VTVF_LIMIT-5" or similar
records_file=$1
rm -f $records_file
for folder in `ls -d */ | sort -n -k1.3`; do
    echo ${folder%%/}
done > $records_file
