# waveform-annotation admin test branch!
Branch for testing admin features of the annotator. Most of the source code and other files are removed to reduce confusion about where to find testing features. Do not make pull requests or merge this branch unless it regards the development of the testing for the admin features. When finished testing, run `git reset --hard admin_practice` to revert back to the original state of the branch to practice some more.

---

## For adding `RECORDS` files to a new data folder
### Move into where the data is stored (if starting in project folder, `waveform-annotation`)
```
cd record-files
```
### Get the scripts to create the annotation folders
```
cp -r old_data_folder/*.sh new_data_folder
```
### Move to the folder with the new data
```
cd new_data_folder
```
### Make sure the `RECORDS` files in each copied script are what you want
### Create all of the `RECORDS` files in the sub-directories and call it `RECORDS_VTVF` ... note, feel free to change the name, you will just have to adjust the `RECORDS_FILE` variable in the `waveform-django/website/settings/base.py` script
```
./sub_records.sh RECORDS_VTVF
```
### Create all the `RECORDS` file in the top-directory and call it `RECORDS_VTVF`
```
./top_records.sh RECORDS_VTVF
```
### Create a blank file to track annotations
```
touch user_assignments.csv
```
### Filter the annotations to be a specific number (pull from `RECORDS_VTVF`, limit of 5 events per record)
```
./filter_anns.sh RECORDS_VTVF 5
```

---

## For merging completed new data folders with existing folders
### Move into where the data is stored (if starting in project folder, `waveform-annotation`)
```
cd record-files
```
### Find if folder names overlap, if they do then change the new folder names and adjust the WFDB files accordingly ... it is okay if you get temporary files such as `.DS_Store`
```
find "old_data_folder/" "merge_data_folder/" -printf '%P\n' | sort | uniq -d
```
### Note, if this fails (especially on Mac) you have have to do the following instead
```
brew install findutils
gfind "old_data_folder/" "merge_data_folder/" -printf '%P\n' | sort | uniq -d
```
### Copy the new data to the old data folder
```
find merge_data_folder/ -mindepth 1 -maxdepth 1 -type d -exec cp -rv {} old_data_folder/ \;
```
### Append the new `RECORDS` to the old `RECORDS`
```
cat merge_data_folder/RECORDS_VTVF >> old_data_folder/RECORDS_VTVF
```
