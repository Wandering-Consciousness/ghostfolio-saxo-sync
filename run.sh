#!/bin/bash

# Wrapper script for cron execution with lock file

set -e

FILE=/root/ghost.lock

if [ ! -f "$FILE" ]; then
   echo "Starting sync execution..."
   touch $FILE
   cd /root && python main.py
   rm $FILE
   echo "Sync execution completed"
else
   echo "Lock file present - another sync is running"
   echo "If this persists, increase time between cron runs"
fi
