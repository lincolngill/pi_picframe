#!/usr/bin/env bash

PID=$(ps -eo pid,args | grep PictureFrame.py | grep -v grep | awk '{print$1}')
if [ -n "$PID" ]; then
   echo "Killing: $PID"
   sudo kill -TERM $PID
else
   echo "No proc found"
fi