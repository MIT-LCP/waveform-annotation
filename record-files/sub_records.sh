#!/bin/sh
# Create RECORDS file for each subfolder based on record names
for folder in */;
do
    rm -f "RECORDS";
    cd $folder;
    for record in `ls -v1 *\.hea | sort -n -t'_' -k2 | cut -d "." -f1`;
    do
        echo $record;
    done > "RECORDS"
    cd ..;
done
