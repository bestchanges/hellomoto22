#!/bin/bash -v

# run this on server side to update server to the latest
. .bashrc
./bestminer-server.sh stop
git pull
pip install -r requirements.txt
sleep 1
python bestminer/distr.py
./bestminer-server.sh start
sleep 2
tail ./bestminer-server.sh.log
./bestminer-server.sh status
