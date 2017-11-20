#!/bin/bash
./bestminer-server.sh stop
git pull
. .bashrc
python make_client_zip.py
./bestminer-server.sh start
