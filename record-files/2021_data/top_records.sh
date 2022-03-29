#!/bin/sh
# Create top-level RECORDS file based on folders
records_file="RECORDS_VTVF_LIMIT-5"
rm -f $records_file
for folder in `ls -d */ | sort -n -k1.3`; do
    echo ${folder%%/}
done > $records_file
