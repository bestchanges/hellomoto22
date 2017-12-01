#!/bin/bash

# run this on server side to update server to the latest
. .bashrc
git pull
pip install -r requirements.txt
./bestminer-server.sh stop
python make_client_zip.py
./bestminer-server.sh start
sleep 3
tail ./bestminer-server.sh.log
./bestminer-server.sh status
