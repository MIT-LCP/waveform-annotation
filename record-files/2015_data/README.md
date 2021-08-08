# record-files
The directory to download remote record files from the 2015 Challenge data and filter for desired events.

## get_anns.sh

- Download the remote files from the 2015 Challenge data hosted on the PhysioNet archive site.
- Replace the "username" and "password" string variables with your actual username and password for the archive site.
- The "Challenge2015ReferenceAnnotations" project should be added to your account so that you can access the files, if not, contact Benjamin Moody for more details on how to set that up.

## filter_anns.sh

- To filter for different signal types, adjust the "ann_types" list variable and change the name of the "out_record_name" string variable to reflect the new output RECORDS file
- If you create a new "out_record_name" and subsequent new RECORDS file, you must change the "RECORDS_FILE" variable in the [settings](https://github.com/MIT-LCP/waveform-annotation/blob/57ac6fbd28cc0ae926daa88dce98776a9826e5de/waveform-django/website/settings/base.py) to update the annotator.

## subfolder.sh

- All of the downloaded data will probably be in only directory which is not desirable.
- Run this shell script to create directories based on the the name of the file (the record name).

## sub_records.sh

- After all of the files have been downloaded and the correct subfolders have been created, create a RECORDS file for each subfolder.

## top_records.sh

- After all of the subfolders have been created, create a top-level directory RECORDS file which references each subfolder with a RECORDS file.
