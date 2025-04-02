import multiprocessing

bind = "0.0.0.0:8000"

# Use eventlet or gevent for WebSockets
worker_class = "eventlet"  # OR "gevent"

workers = 1  # Recommended worker count
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"

