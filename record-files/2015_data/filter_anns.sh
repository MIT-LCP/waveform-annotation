#!/bin/sh
# All the desired types of annotations
ann_types="VTach\|VFib"
out_record_name="RECORDS_VTVF"

# Get all of the folders with the desired annotation type
folders=$(grep -r --include="*.hea" "$ann_types" . | cut -d : -f1 | cut -d / -f2 | uniq | sort -n -t e -k2)
echo $folders | tr " " "\n" >> $out_record_name
for folder in $folders; do
    # Create a new RECORDS file for each subfolder
    grep -ir --include="*.hea" "$ann_types" $folder | cut -d : -f1 | cut -d / -f2 | cut -d . -f1 | uniq | sort -n -t _ -k2 > $folder/$out_record_name
    # Add the folder name to the top of the RECORDS file
    echo $folder | cat - $folder/$out_record_name > temp && mv temp $folder/$out_record_name
done
