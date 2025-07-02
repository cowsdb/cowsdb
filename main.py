import os
import signal
import tempfile
from chdb import session as chs
from flask import Flask, request, Response, g
from flask_httpauth import HTTPBasicAuth

os.environ['VITE_CLICKHOUSE_SELFSERVICE'] = 'true'
app = Flask(__name__, static_folder="public", static_url_path="")
auth = HTTPBasicAuth()

# Store connections
connections = {}

def signal_handler(signum, frame):
    print("\nCleaning up connections...")
    for conn in connections.values():
        try:
            conn.close()
        except Exception:
            pass
    print("Exiting...")
    os._exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@auth.verify_password
def verify(username, password):
    # PATCH: Close previous session if it exists before opening a new one
    old_driver = getattr(g, "driver", None)
    if old_driver is not None:
        try:
            old_driver.close()
        except Exception:
            pass

    if not (username and password):
        # Stateless session for unauthenticated
        g.driver = chs.Session()
    else:
        path = globals()["path"] + "/" + str(hash(username + password))
        sess = connections.get(path)
        if sess is None:
            # Create a new session only if it doesn't exist for this user
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

        # chdb.session.Session.query returns bytes
        result = driver.query(query, format)
        # Ensure result is bytes
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
        # Always return bytes or string
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

app.run(host=host, port=port)
