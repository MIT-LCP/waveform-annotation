#!/bin/sh
# Create subfolders based on record name
for file in *;
do
    dir = $(echo $file | cut -d"_" -f1);
    echo $dir;
    mkdir -p $dir;
    mv $file $dir;
done
