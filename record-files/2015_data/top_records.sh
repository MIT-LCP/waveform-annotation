#!/bin/sh
# Create top-level RECORDS file based on folders
rm -f "RECORDS"
for folder in `ls -d */ | sort -n -k1.3`;
do
    echo ${folder%%/};
done > "RECORDS"
