#!/bin/bash

# read sensitive authorization data from environment variables
owncloud_home=$OWNCLOUD_URL
usr=$OWNCLOUD_USERNAME
pwd=$OWNCLOUD_PASSWORD
build_dir="$owncloud_home/latex-builds"
auth="$usr:$pwd"
echo "auth - $auth"  # uncomment to check if username and password are correct

# first argument to script is path to destination (on owncloud), relative to build_dir
destpath=$1

# second argument is path to source file (on local machine), that needs to be uploaded
srcpath=$2


curl -Ss -u "$auth" -X PUT "$build_dir/$destpath" --data-binary @"$srcpath"
file_exists=$(curl -s -o /dev/null -u "$auth" -I -w "%{http_code}" "$build_dir/$destpath")
if [ "$file_exists" -eq "200" ]; then
  echo "$srcpath -> $destpath uploaded successfully"
  exit 0
else
  echo "$srcpath -> $destpath upload failed"
  exit 1
fi;
