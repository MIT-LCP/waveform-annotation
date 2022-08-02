#!/bin/sh
# Create RECORDS file for each subfolder based on record names
# Should be "RECORDS_VTVF_LIMIT-5" or similar
records_file=$1
for folder in */; do
    cd $folder
    rm -f $records_file
    for record in `ls -v1 *\.hea | sort -n -t'_' -k2 | cut -d "." -f1`; do
        echo $record
    done > $records_file
    cd ..
done
