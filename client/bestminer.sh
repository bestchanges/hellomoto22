#!/bin/bash
while true ; do
echo "Starting BestMiner miner."
python3 bestminer-client.py
if [ $? -eq 200 ] ; then
        echo "Going to install update of bestminer"
        if [ -d 'update' ] ; then
                cp -rv ./update/* .
        else
                echo "Error update. No 'update' directory exists."
        fi
fi
echo "BestMiner exited. Going to restart..."
sleep 5
done
