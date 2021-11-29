#!/bin/sh
# All the desired types of annotations
ann_types="VTach\|VFib"
out_record_name="RECORDS_VTVF"
saved_recs=$(tail -n +2 all_anns.csv | cut -d , -f3-4)

# Get all of the folders with the desired annotation type
folders=$(grep -r --include="*.hea" "$ann_types" . | cut -d : -f1 | cut -d / -f2 | uniq | sort -n -t e -k2)
echo $folders | tr " " "\n" > $out_record_name

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
        events=$(grep -ir --include="*.hea" "$ann_types" $folder | cut -d : -f1 | cut -d / -f2 | cut -d . -f1 | sort -n -t _ -k2 | uniq)
        if [ $lines -eq 1 ]; then
            shuf -n $add -e $events >> $folder/$out_record_name
        else
            # echo $(tail -n +2 $folder/$out_record_name) $(shuf -n $add -e $events) | tr uniq -c | sort -rn
            # echo LOL
            present=$(tail -n +2 $folder/$out_record_name)
            rand=$(shuf -n $add -e $events)
            assign_set=$(echo $present $rand)
            repeats=$(echo $assign_set | tr ' ' '\n' | sort -rn | uniq -c | sort -rn | head -n 1 | cut -d' ' -f7)
            
            while [ $repeats -gt 1 ]; do
                rand=$(shuf -n $add -e $events)
                assign_set=$(echo $present $rand)
                repeats=$(echo $assign_set | tr ' ' '\n' | sort -rn | uniq -c | sort -rn | head -n 1 | cut -d' ' -f7)
            done

            echo $rand | tr ' ' '\n' | sort >> $folder/$out_record_name

        fi
    fi
    # Add the folder name to the top of the RECORDS file
    # echo $folder | cat - $folder/$out_record_name > temp && mv temp $folder/$out_record_name
done
