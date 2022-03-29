#!/bin/sh
# Merge one folder's records into another
folder_new="test_data"
folder_merge_into="2015_data"

# Create the RECORDS files
# cd folder_new
# ./top_records.sh
# ./sub_records.sh
# ./filter_anns.sh
# cd ..

# Copy all of the records directories and events
find $folder_new/ -mindepth 1 -type d | xargs -I {} cp -R {} $folder_merge_into/

# Merge all of the RECORDS files
all_records_files=$(find test_data/RECORDS* -type f)
for current_record_path in $all_records_files; do
    current_record=$(echo $current_record_path | cut -d / -f2)
    cat $current_record_path >> $folder_merge_into/$current_record
done
