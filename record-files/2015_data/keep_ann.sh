#!/bin/sh
# All the desired types of annotations
ann_types="VTach\|VFib"
out_record_name="RECORDS_VTVF"
saved_recs=$(tail -n +2 all_anns.csv | cut -d , -f3-4)

# Get all of the folders with the desired annotation type
folders=$(grep -r --include="*.hea" "$ann_types" . | cut -d : -f1 | cut -d / -f2 | uniq | sort -n -t e -k2)
echo $folders | tr " " "\n" >> $out_record_name

# Clear list of events that can be assigned
for folder in $folders; do
    echo $folder > $folder/$out_record_name
done

# Give priority to events that already have annotations
for info in $saved_recs; do
    rec=$(echo $info | cut -d , -f1)
    event=$(echo $info | cut -d , -f2)
    echo $event >> $rec/$out_record_name
done

# Randomly select events such that only
for folder in $folders; do
    # Create a new RECORDS file for each subfolder
    lines=$(wc -l $folder/$out_record_name | cut -d ' ' -f1)
    limit=6
    if [ $lines -lt $limit ]; then
        add=$(expr 6 - $lines)
        grep -ir --include="*.hea" "$ann_types" $folder | cut -d : -f1 | cut -d / -f2 | cut -d . -f1 | uniq | sort -n -t _ -k2 | shuf -n $add >> $folder/$out_record_name
    fi
    # Add the folder name to the top of the RECORDS file
    # echo $folder | cat - $folder/$out_record_name > temp && mv temp $folder/$out_record_name
done
