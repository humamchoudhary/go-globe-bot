# # import multiprocessing
#
# bind = "0.0.0.0:5000"
#
# # Use eventlet or gevent for WebSockets
# worker_class = "eventlet"  # OR "gevent"
#
# workers = 1  # Recommended worker count
# accesslog = "logs/access.log"
# errorlog = "logs/error.log"
# loglevel = "info"
#
# import multiprocessing

bind = "0.0.0.0:5000"

# Use eventlet or gevent for WebSockets
worker_class = "eventlet"  # OR "gevent"

workers = 1  # Recommended worker count

logfile = "logs/gunicorn.log"
accesslog = logfile
errorlog = logfile
loglevel = "info"

