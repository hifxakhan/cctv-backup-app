# gunicorn.conf.py
# Single worker for Socket.IO compatibility with threading mode
# Multiple workers cause "Invalid session" errors because each worker
# has its own in-memory session state
bind = "0.0.0.0:10000"
workers = 1
threads = 4
timeout = 120