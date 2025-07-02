import os
import signal
import tempfile
import atexit
from chdb import session as chs
from flask import Flask, request, Response, g
from flask_httpauth import HTTPBasicAuth
from cachetools import TTLCache

os.environ['VITE_CLICKHOUSE_SELFSERVICE'] = 'true'
app = Flask(__name__, static_folder="public", static_url_path="")
auth = HTTPBasicAuth()

# Store connections with TTL (1 hour), max 1000 sessions
timeout_seconds = int(os.getenv('SESSION_TTL', '3600'))
connections = TTLCache(maxsize=1000, ttl=timeout_seconds)

# --- Cleanup logic for all sessions ---
def cleanup_connections():
    print("\nCleaning up connections...")
    for conn in list(connections.values()):
        try:
            conn.close()
        except Exception:
            pass
    print("All sessions closed.")

# Register cleanup for process exit (works for most WSGI servers)
atexit.register(cleanup_connections)

# Gunicorn worker exit hook (if running under Gunicorn)
def on_gunicorn_worker_exit(server, worker):
    cleanup_connections()

# If running under Gunicorn, try to register the worker exit hook
def try_register_gunicorn_hook():
    if 'gunicorn' in os.environ.get('SERVER_SOFTWARE', '').lower():
        try:
            import gunicorn.app.base
            gunicorn.app.base.Worker.on_exit = staticmethod(on_gunicorn_worker_exit)
        except Exception:
            pass
try_register_gunicorn_hook()

@auth.verify_password
def verify(username, password):
    old_driver = getattr(g, "driver", None)
    if old_driver is not None:
        try:
            old_driver.close()
        except Exception:
            pass

    if not (username and password):
        g.driver = chs.Session()
    else:
        path = globals()["path"] + "/" + str(hash(username + password))
        sess = connections.get(path)
        if sess is None:
            sess = chs.Session()
            connections[path] = sess
        g.driver = sess
    return True

def chdb_query_with_errmsg(query, format):
    try:
        driver = getattr(g, "driver", None)
        if driver is None:
            driver = chs.Session()
        new_stderr = tempfile.TemporaryFile()
        old_stderr_fd = os.dup(2)
        os.dup2(new_stderr.fileno(), 2)

        result = driver.query(query, format)
        if not isinstance(result, (bytes, str)):
            result = str(result).encode()

        new_stderr.flush()
        new_stderr.seek(0)
        errmsg = new_stderr.read()

        new_stderr.close()
        os.dup2(old_stderr_fd, 2)
    except Exception as e:
        print(f"An error occurred: {e}")
        result = b""
        errmsg = str(e).encode()

    return result, errmsg

@app.route('/', methods=["GET"])
@auth.login_required
def clickhouse():
    query = request.args.get('query', default="", type=str)
    format = request.args.get('default_format', default="TSV", type=str)
    database = request.args.get('database', default="", type=str)
    if not query:
        return app.send_static_file('index.html')
    if database:
        query = f"USE {database}; {query}"
    result, errmsg = chdb_query_with_errmsg(query.strip(), format)
    if len(errmsg) == 0:
        return Response(result, content_type='text/plain'), 200
    if len(result) > 0:
        print("warning:", errmsg)
        return Response(result, content_type='text/plain'), 200
    return Response(errmsg, content_type='text/plain'), 400

@app.route('/', methods=["POST"])
@auth.login_required
def play():
    query = request.args.get('query', default=None, type=str)
    body = request.get_data() or None
    format = request.args.get('default_format', default="TSV", type=str)
    database = request.args.get('database', default="", type=str)
    if query is None:
        query = ""
    if body is not None:
        query = body.decode('utf-8').strip()
    if not query:
        return "Error: no query parameter provided", 400
    if database:
        query = f"USE {database}; {query}"
    result, errmsg = chdb_query_with_errmsg(query.strip(), format)
    if len(errmsg) == 0:
        return Response(result, content_type='text/plain'), 200
    if len(result) > 0:
        print("warning:", errmsg)
        return Response(result, content_type='text/plain'), 200
    return Response(errmsg, content_type='text/plain'), 400

@app.route('/play', methods=["GET"])
def handle_play():
    return app.send_static_file('index.html')

@app.route('/ping', methods=["GET"])
def handle_ping():
    return "Ok", 200

@app.errorhandler(404)
def handle_404(e):
    return app.send_static_file('index.html')

host = os.getenv('HOST', '0.0.0.0')
port = os.getenv('PORT', 8123)
path = os.getenv('DATA', '.chdb_data')

# ---
# NOTE: Do NOT use app.run() in production. Use Gunicorn:
#   gunicorn -w 4 -b 0.0.0.0:8123 main:app
# ---

app.run(host=host, port=port)
