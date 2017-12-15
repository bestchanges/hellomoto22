BESTMINER_PLATFORM=production
export BESTMINER_PLATFORM
 ~/.virtualenvs/bestminer/bin/gunicorn --bind 0.0.0.0:5000 -k gevent --daemon --pid gunicorn.sh.pid \
	 --access-logfile log/access.log --error-logfile gunicorn.sh.err --capture-output \
	 --graceful-timeout 7 bestminer:app

