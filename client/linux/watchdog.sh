#!/bin/bash
PORT=/dev/ttyACM0
if [ ! -c $PORT ] ; then
        echo "No open-dev compatible watchdog detected"
        exit 1
fi
while true
do
 echo -n "~U" > $PORT
 sleep 3
done
