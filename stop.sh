#!/bin/bash

# Find the PID of the python process running app.py
PID=$(pgrep -f 'app.py')

# Kill the process if it's running
if [ -n "$PID" ]; then
    echo "Killing process $PID"
    kill -9 $PID
else
    echo "No process found for app.py"
fi