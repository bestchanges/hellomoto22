#!/bin/bash

# run this on server side to update server to the latest

./bestminer-server.sh stop
git pull
. .bashrc
python make_client_zip.py
./bestminer-server.sh start
