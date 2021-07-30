#!/bin/sh
# Get folder .hea and .cba files based on record name
# Replace &&& with username and $$$ with password
username = &&&;
password = $$$;
for folder in */;
do
    cd $folder;
    wget --http-user $username --http-password $password https://archive.physionet.org/works/Challenge2015ReferenceAnnotations/files/ge/${folder%%/}.hea;
    wget --http-user $username --http-password $password https://archive.physionet.org/works/Challenge2015ReferenceAnnotations/files/ge/${folder%%/}.cba;
    cd ..;
done
