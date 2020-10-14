#!/bin/bash

# read sensitive authorization data from environment variables
owncloud_home=$OWNCLOUD_URL
usr=$OWNCLOUD_USERNAME
pwd=$OWNCLOUD_PASSWORD
build_dir="$owncloud_home/latex-builds"
auth="$usr:$pwd"
#echo "auth - $auth"  # uncomment to check if username and password are correct

# first argument to script is directory name on owncloud within `build_dir`
dirname=$1


dir_exists=$(curl -s -o /dev/null -u "$auth" -I -w "%{http_code}" "$build_dir/$dirname")
if [ "$dir_exists" == "200" ]; then
  echo "dir $dirname already exists"
  exit 0
else
  curl -u "$usr:$pwd" -X MKCOL "$build_dir/$dirname" -o cloud_mkdir.out
  curl_retcode=$?
  if [ "$curl_retcode" -eq "0" ]; then
    echo "dir $dirname created"
    exit 0
  else
    echo "dir $dirname creation failed"
    exit 1
  fi
fi