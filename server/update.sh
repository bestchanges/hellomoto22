#!/bin/bash -v

# run this on server side to update server to the latest
. .bashrc
git pull
pip install -r requirements.txt
sleep 4
./bestminer-server.sh stop
python bestminer/distr.py
./bestminer-server.sh start
sleep 3
tail ./bestminer-server.sh.log
./bestminer-server.sh status
