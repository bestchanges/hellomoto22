BESTMINER_PLATFORM=production
export BESTMINER_PLATFORM
. ~/.virtualenvs/bestminer/bin/activate
# increase number of open files for server
ulimit -Sn 10000
