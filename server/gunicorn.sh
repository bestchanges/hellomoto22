gunicorn --bind 0.0.0.0:5000 -k gevent --daemon --pid gunicorn.pid --threads 1 bestminer:app
