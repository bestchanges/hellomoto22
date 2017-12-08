import logging.handlers

logging.basicConfig(format='%(asctime)-10s|%(name)-10s|%(levelname)s|%(message)s', level=logging.DEBUG)

l = logging.getLogger("bestminer")
l.setLevel(logging.DEBUG)

l = logging.getLogger("werkzeug")
h = logging.handlers.TimedRotatingFileHandler("log/web_server.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.propagate = False

l = logging.getLogger('bestminer.rig_manager')
l.setLevel(logging.DEBUG)
h = logging.handlers.TimedRotatingFileHandler("log/rig_manager.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.addHandler(h)

l = logging.getLogger('bestminer.benchmark_manager')
l.setLevel(logging.DEBUG)
h = logging.handlers.TimedRotatingFileHandler("log/benchmark_server.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.addHandler(h)

l = logging.getLogger('bestminer.logging_server')
l.setLevel(logging.DEBUG)
h = logging.handlers.TimedRotatingFileHandler("log/logging_server.log", backupCount=7, when='midnight',
                                              encoding='utf-8')
h.setFormatter(logging.Formatter('%(asctime)-10s|%(levelname)s|%(message)s)'))
l.addHandler(h)

