#!/bin/sh
# All the desired types of annotations
out_record_name="RECORDS_VTVF_LIMIT-5"
limit=5
saved_events=$(tail -n +2 all_anns.csv | cut -d , -f4 | sort | uniq)

# Get all of the folders with the desired annotation type
folders=$(grep -r --include="*.hea" . | cut -d : -f1 | cut -d / -f1 | uniq | sort -n -t e -k2)
echo $folders | tr " " "\n" > $out_record_name

# Clear list of events that can be assigned
for folder in $folders; do
    echo $folder > $folder/$out_record_name
done

# Give priority to events that already have annotations
saved_events=($saved_events)
for folder in $folders; do
    rec_events=()
    for e in "${saved_events[@]}"; do [[ $e == "$folder"* ]] && rec_events+=("$e"); done
    shuffled_events=$(shuf -n $limit -e ${rec_events[@]} | sort)
    for event in $shuffled_events; do
        echo $event >> $folder/$out_record_name
    done
done

# Randomly select events such that only
for folder in $folders; do
    # Create a new RECORDS file for each subfolder
    lines=$(wc -l $folder/$out_record_name | cut -d ' ' -f1)
    if [ $lines -le $limit ]; then
        add=$(expr $limit - $lines + 1)
        events=$(grep -ir --include="*.hea" "$ann_types" $folder | cut -d : -f1 | cut -d / -f2 | cut -d . -f1 | sort -n -t _ -k2 | uniq)
	n_events=$(echo $events | tr " " "\n" | wc -l)
	if [[ $lines -eq 1 || $n_events -le $limit ]]; then
            echo $folder > $folder/$out_record_name
            shuf -n $add -e $events | sort >> $folder/$out_record_name
        else    
            present=$(tail -n +2 $folder/$out_record_name)
	    rand=$(shuf -n $add -e $events)
            assign_set=$(echo $present $rand)
            repeats=$(echo $assign_set | tr ' ' '\n' | sort -rn | uniq -c | sort -rn | head -n 1 | cut -d' ' -f7)
            while [ $repeats -gt 1 ]; do
		rand=$(shuf -n $add -e $events)
                assign_set=$(echo $present $rand)
		assign_len=$(echo $assign_set | wc -w)
                if [ $assign_len -le $limit ]; then
		    break
		fi
		repeats=$(echo $assign_set | tr ' ' '\n' | sort -rn | uniq -c | sort -rn | head -n 1 | cut -d' ' -f7)
	    done

	    echo $rand | tr ' ' '\n' | sort >> $folder/$out_record_name

        fi
    fi
    # Add the folder name to the top of the RECORDS file
done
