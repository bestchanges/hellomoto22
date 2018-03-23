#!/bin/bash -v

# run this on server side to update server to the latest
. .bashrc
./gunicorn1.sh stop
git pull
pip install -r requirements.txt
sleep 1
python bestminer/distr.py
./gunicorn1.sh start
sleep 2
#tail ./bestminer-server.sh.log
./gunicorn1.sh status
