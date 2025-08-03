#!/usr/bin/env python3
"""
CowsDB - ClickHouse HTTP API and Native Protocol Server
A server wrapper for chdb that emulates ClickHouse HTTP API and Native Protocol
Refactored for chdb 3.4.0+ which doesn't support multiple concurrent sessions
"""

import os
import sys
import tempfile
import threading
import socket
import struct
import signal
from typing import List, Tuple

os.environ['VITE_CLICKHOUSE_SELFSERVICE'] = 'true'

from flask import Flask, request, Response, g
from flask_httpauth import HTTPBasicAuth

import chdb.session as chs

# Global variables
host = "0.0.0.0"
port = 8123
native_port = 9000
base_path = "/tmp/cowsdb"
native_server = None

# Global session manager - maintains one session per auth pair
session_manager = {}
session_lock = threading.Lock()

# Flask app setup
app = Flask(__name__, static_folder="public", static_url_path="")
auth = HTTPBasicAuth()

# Native protocol constants
class ClientPacketTypes:
    HELLO = 0
    QUERY = 1
    DATA = 2
    CANCEL = 3
    PING = 4
    TABLES_STATUS_REQUEST = 5

class ServerPacketTypes:
    HELLO = 0
    DATA = 1
    EXCEPTION = 2
    PROGRESS = 3
    PONG = 4
    END_OF_STREAM = 5
    PROFILE_INFO = 6
    TOTALS = 7
    EXTREMES = 8
    TABLES_STATUS_RESPONSE = 9
    LOG = 10
    TABLE_COLUMNS = 11
    PART_UUIDS = 12
    READ_TASK_REQUEST = 13
    PROFILE_EVENTS = 14
    MERGE_TREE_ALL_RANGES_ANNOUNCEMENT = 15
    MERGE_TREE_READ_TASK_REQUEST = 16
    TIMEZONE_UPDATE = 17

# Protocol version constants
DBMS_NAME = 'CowsDB'
DBMS_VERSION_MAJOR = 25
DBMS_VERSION_MINOR = 5
DBMS_VERSION_PATCH = 2
DBMS_REVISION = 54468

# Protocol revision constants
DBMS_MIN_REVISION_WITH_SERVER_TIMEZONE = 54058
DBMS_MIN_REVISION_WITH_SERVER_DISPLAY_NAME = 54372
DBMS_MIN_REVISION_WITH_VERSION_PATCH = 54401
DBMS_MIN_PROTOCOL_VERSION_WITH_PASSWORD_COMPLEXITY_RULES = 54461
DBMS_MIN_REVISION_WITH_INTERSERVER_SECRET_V2 = 54462

class DataBlock:
    """Represents a data block in ClickHouse native format"""
    def __init__(self, columns: List[Tuple[str, List]], table_name: str = ""):
        self.columns = columns
        self.table_name = table_name
    
    def to_bytes(self) -> bytes:
        """Convert block to native protocol bytes"""
        result = b""
        
        # Number of columns
        result += struct.pack('<I', len(self.columns))
        
        # Number of rows
        if self.columns:
            num_rows = len(self.columns[0][1])
        else:
            num_rows = 0
        result += struct.pack('<I', num_rows)
        
        # Column data
        for column_name, column_data in self.columns:
            # Column name
            name_bytes = column_name.encode('utf-8')
            result += struct.pack('<I', len(name_bytes))
            result += name_bytes
            
            # Column type (simplified - always String for now)
            type_name = "String"
            type_bytes = type_name.encode('utf-8')
            result += struct.pack('<I', len(type_bytes))
            result += type_bytes
            
            # Column data
            for value in column_data:
                if value is None:
                    result += struct.pack('<I', 0)  # NULL
                else:
                    value_str = str(value)
                    value_bytes = value_str.encode('utf-8')
                    result += struct.pack('<I', len(value_bytes))
                    result += value_bytes
        
        return result

def get_user_session_path(username: str = None, password: str = None) -> str:
    """Get the session path for a user based on authentication"""
    # Default to "default:" when unset
    if not username:
        username = "default"
    if not password:
        password = "default"
    
    # All users get a path based on their credentials hash
    user_hash = str(hash(username + ":" + password))
    return os.path.join(base_path, user_hash)

def get_or_create_session(username: str = None, password: str = None):
    """Get or create a persistent session for the user"""
    # Default to "default:" when unset
    if not username:
        username = "default"
    if not password:
        password = "default"
    
    auth_key = f"{username}:{password}"
    
    with session_lock:
        if auth_key not in session_manager:
            # Create new session
            session_path = get_user_session_path(username, password)
            os.makedirs(session_path, exist_ok=True)
            session = chs.Session(path=session_path)
            session_manager[auth_key] = session
            print(f"🔧 Created new persistent session for {auth_key} at {session_path}")
        else:
            print(f"🔧 Using existing persistent session for {auth_key}")
        
        return session_manager[auth_key]

def execute_query_with_session(query: str, format: str = "TSV", username: str = None, password: str = None):
    """Execute a query using a persistent session for the user"""
    try:
        # Get or create persistent session
        session = get_or_create_session(username, password)
        
        # Execute the query
        print(f"🔍 Executing query: {query}")
        print(f"   User: {username or 'default'}")
        
        result = session.query(query, format)
        
        # Check if the result has an error
        try:
            if hasattr(result, 'has_error') and result.has_error():
                error_msg = result.error_message() if hasattr(result, 'error_message') else "Unknown error"
                print(f"❌ Query returned error: {error_msg}")
                print(f"   Query: {query}")
                print(f"   Format: {format}")
                print(f"   User: {username}")
                return b""  # Return empty bytes for errors
        except Exception as check_error:
            print(f"⚠️  Could not check for errors: {check_error}")
        
        # Get the bytes
        bytes_result = result.bytes()
        print(f"✅ Query successful, returned {len(bytes_result)} bytes")
        return bytes_result
        
    except Exception as e:
        # Log the error to help with debugging
        print(f"❌ Query execution error: {e}")
        print(f"   Query: {query}")
        print(f"   Format: {format}")
        print(f"   User: {username}")
        return b""  # Return empty bytes for errors

class NativeProtocolServer:
    def __init__(self, host='0.0.0.0', port=9000):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.client_revision = None  # Store client revision from handshake
        self.current_user = None
        self.current_password = None
        
    def start(self):
        """Start the native protocol server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"Native protocol server listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                client_socket, address = self.server_socket.accept()
                print(f"Native connection from {address}")
                
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
                
        except Exception as e:
            print(f"Native server error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("Native protocol server stopped")
    
    def handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle a single client connection"""
        try:
            if not self.perform_handshake(client_socket):
                return
            
            print(f"Native client {address} authenticated as {self.current_user}:{self.current_password}")
            
            while self.running:
                try:
                    packet_type = self.read_varint(client_socket)
                    
                    if packet_type == ClientPacketTypes.QUERY:
                        self.handle_query(client_socket, address)
                    elif packet_type == ClientPacketTypes.PING:
                        self.handle_ping(client_socket)
                    elif packet_type == ClientPacketTypes.CANCEL:
                        self.handle_cancel(client_socket)
                    elif packet_type == ClientPacketTypes.HELLO:
                        # Handle subsequent HELLO packets (re-authentication)
                        if not self.perform_handshake(client_socket):
                            break
                    else:
                        print(f"Unsupported packet type: {packet_type}")
                        break
                        
                except Exception as e:
                    print(f"Error handling native client {address}: {e}")
                    break
                    
        except Exception as e:
            print(f"Error with native client {address}: {e}")
        finally:
            client_socket.close()
            print(f"Native connection closed for {address}")
    
    def perform_handshake(self, client_socket: socket.socket) -> bool:
        """Perform protocol handshake with client"""
        try:
            # Read client hello
            packet_type = self.read_varint(client_socket)
            if packet_type != ClientPacketTypes.HELLO:
                print(f"Expected HELLO packet, got {packet_type}")
                return False
            
            # Read client info
            client_name = self.read_binary_str(client_socket)
            client_version_major = self.read_varint(client_socket)
            client_version_minor = self.read_varint(client_socket)
            client_revision = self.read_varint(client_socket)
            database = self.read_binary_str(client_socket)
            user = self.read_binary_str(client_socket)
            password = self.read_binary_str(client_socket)
            
            # Store authentication info for session management
            self.current_user = user
            self.current_password = password
            
            # Store client revision for use in query handling
            self.client_revision = client_revision
            
            print(f"Native client: {client_name} v{client_version_major}.{client_version_minor} (rev {client_revision})")
            print(f"User: {user}, Database: {database}, Password: '{password}'")
            
            # Calculate used revision
            used_revision = min(client_revision, DBMS_REVISION)
            
            # Send server hello
            self.write_varint(ServerPacketTypes.HELLO, client_socket)
            self.write_binary_str(DBMS_NAME, client_socket)
            self.write_varint(DBMS_VERSION_MAJOR, client_socket)
            self.write_varint(DBMS_VERSION_MINOR, client_socket)
            self.write_varint(DBMS_REVISION, client_socket)
            
            # Send timezone if supported
            if used_revision >= DBMS_MIN_REVISION_WITH_SERVER_TIMEZONE:
                self.write_binary_str("UTC", client_socket)
            
            # Send display name if supported
            if used_revision >= DBMS_MIN_REVISION_WITH_SERVER_DISPLAY_NAME:
                self.write_binary_str(DBMS_NAME, client_socket)
            
            # Send version patch if supported
            if used_revision >= DBMS_MIN_REVISION_WITH_VERSION_PATCH:
                self.write_varint(DBMS_VERSION_PATCH, client_socket)
            
            # Send password complexity rules if supported
            if used_revision >= DBMS_MIN_PROTOCOL_VERSION_WITH_PASSWORD_COMPLEXITY_RULES:
                self.write_varint(0, client_socket)  # No rules
            
            # Send inter-server secret if supported
            if used_revision >= DBMS_MIN_REVISION_WITH_INTERSERVER_SECRET_V2:
                self.write_uint64(0, client_socket)  # No nonce
            
            return True
            
        except Exception as e:
            print(f"Native handshake failed: {e}")
            return False
    
    def handle_query(self, client_socket: socket.socket, address: tuple):
        """Handle a query from the client"""
        try:
            # Use the actual client revision from handshake
            client_revision = self.client_revision or 54468
            
            # Read query info
            query_id = self.read_binary_str(client_socket)
            
            # Read client info if supported (for newer protocol versions)
            if client_revision >= 54032:  # DBMS_MIN_REVISION_WITH_CLIENT_INFO
                # Read client info
                query_kind = self.read_uint8(client_socket)
                if query_kind != 0:  # Not empty
                    initial_user = self.read_binary_str(client_socket)
                    initial_query_id = self.read_binary_str(client_socket)
                    initial_address = self.read_binary_str(client_socket)
                    
                    # Read initial query start time if supported
                    if client_revision >= 54449:  # DBMS_MIN_PROTOCOL_VERSION_WITH_INITIAL_QUERY_START_TIME
                        initial_query_start_time = self.read_uint64(client_socket)
                    
                    interface = self.read_uint8(client_socket)
                    os_user = self.read_binary_str(client_socket)
                    client_hostname = self.read_binary_str(client_socket)
                    client_name = self.read_binary_str(client_socket)
                    client_version_major = self.read_varint(client_socket)
                    client_version_minor = self.read_varint(client_socket)
                    client_revision = self.read_varint(client_socket)
                    
                    # Read quota key if supported
                    if client_revision >= 54060:  # DBMS_MIN_REVISION_WITH_QUOTA_KEY_IN_CLIENT_INFO
                        quota_key = self.read_binary_str(client_socket)
                    
                    # Read distributed depth if supported
                    if client_revision >= 54448:  # DBMS_MIN_PROTOCOL_VERSION_WITH_DISTRIBUTED_DEPTH:
                        distributed_depth = self.read_varint(client_socket)
            
            # Read settings
            settings_as_strings = client_revision >= 54429  # DBMS_MIN_REVISION_WITH_SETTINGS_SERIALIZED_AS_STRINGS
            settings = {}
            while True:
                setting_name = self.read_binary_str(client_socket)
                if not setting_name:  # End of settings
                    break
                
                if settings_as_strings:
                    flags = self.read_uint8(client_socket)
                    setting_value = self.read_binary_str(client_socket)
                else:
                    # For non-string settings, we'd need to know the type
                    # For now, just skip them
                    continue
                
                settings[setting_name] = setting_value
            
            # Read inter-server secret if supported
            if client_revision >= 54441:  # DBMS_MIN_REVISION_WITH_INTERSERVER_SECRET
                inter_server_secret = self.read_binary_str(client_socket)
            
            # Read processing stage and compression
            processing_stage = self.read_varint(client_socket)
            compression = self.read_varint(client_socket)
            
            # Read the actual query
            query = self.read_binary_str(client_socket)
            
            # Read parameters if supported
            if client_revision >= 54459:  # DBMS_MIN_PROTOCOL_VERSION_WITH_PARAMETERS
                # Read custom settings (parameters)
                while True:
                    param_name = self.read_binary_str(client_socket)
                    if not param_name:  # End of parameters
                        break
                    flags = self.read_uint8(client_socket)
                    param_value = self.read_binary_str(client_socket)
            
            # Execute query using the global session manager
            try:
                print(f"🔍 Executing native query: {query}")
                
                # Get or create persistent session for this client's auth
                session = get_or_create_session(self.current_user, self.current_password)
                
                # Execute query using the persistent session
                result = session.query(query, "Native").bytes()
                
                # Since execute_query_with_session returns bytes directly, 
                # we assume success if we get bytes (no error checking needed)
                if isinstance(result, bytes):
                    # Success - we have data
                    try:
                        # result is already bytes from execute_query_with_session
                        native_data = result
                        
                        # Send data packet with proper ClickHouse native protocol structure
                        self.write_varint(ServerPacketTypes.DATA, client_socket)
                        self.write_binary_str("", client_socket)  # table name
                        self.write_varint(0, client_socket)  # block info
                        
                        # Send the native binary data as the block content
                        client_socket.send(native_data)
                        
                        # Send end of stream
                        self.write_varint(ServerPacketTypes.END_OF_STREAM, client_socket)
                    except Exception as e:
                        # Send exception
                        self.write_varint(ServerPacketTypes.EXCEPTION, client_socket)
                        self.write_binary_str(f"Failed to get query data: {str(e)}", client_socket)
                else:
                    # This shouldn't happen, but handle it gracefully
                    self.write_varint(ServerPacketTypes.EXCEPTION, client_socket)
                    self.write_binary_str("Unexpected result type", client_socket)
                    return
                
            except Exception as e:
                # Log the error
                print(f"❌ Native query execution failed: {e}")
                print(f"   Query: {query}")
                # Send exception
                self.write_varint(ServerPacketTypes.EXCEPTION, client_socket)
                # Send error as string, not binary
                error_str = str(e)
                self.write_binary_str(error_str, client_socket)
            
        except Exception as e:
            print(f"Error handling native query: {e}")
            # Send exception
            try:
                self.write_varint(ServerPacketTypes.EXCEPTION, client_socket)
                self.write_binary_str(str(e), client_socket)
            except:
                pass
    
    def handle_ping(self, client_socket: socket.socket):
        """Handle ping from client"""
        self.write_varint(ServerPacketTypes.PONG, client_socket)
    
    def handle_cancel(self, client_socket: socket.socket):
        """Handle cancel request from client"""
        print("Native query cancel requested")
    
    # Protocol helper methods
    def read_uint8(self, sock: socket.socket) -> int:
        """Read an 8-bit unsigned integer"""
        data = sock.recv(1)
        if not data:
            raise ConnectionError("Connection closed by peer")
        return data[0]
    
    def read_uint64(self, sock: socket.socket) -> int:
        """Read a 64-bit unsigned integer"""
        data = sock.recv(8)
        if len(data) != 8:
            raise ConnectionError("Connection closed by peer")
        return struct.unpack('<Q', data)[0]
    
    def read_varint(self, sock: socket.socket) -> int:
        """Read a variable-length integer"""
        result = 0
        shift = 0
        while True:
            data = sock.recv(1)
            if not data:
                raise ConnectionError("Connection closed by peer")
            byte = data[0]
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        return result
    
    def write_varint(self, value: int, sock: socket.socket):
        """Write a variable-length integer"""
        while value >= 0x80:
            sock.send(bytes([(value & 0x7F) | 0x80]))
            value >>= 7
        sock.send(bytes([value]))
    
    def write_uint64(self, value: int, sock: socket.socket):
        """Write a 64-bit unsigned integer"""
        sock.send(struct.pack('<Q', value))
    
    def read_binary_str(self, sock: socket.socket) -> str:
        """Read a binary string"""
        length = self.read_varint(sock)
        if length == 0:
            return ""
        data = sock.recv(length)
        if len(data) != length:
            raise ConnectionError("Connection closed by peer")
        return data.decode('utf-8')
    
    def write_binary_str(self, value: str, sock: socket.socket):
        """Write a binary string"""
        if isinstance(value, str):
            value = value.encode('utf-8')
        self.write_varint(len(value), sock)
        sock.send(value)

@auth.verify_password
def verify(username, password):
    # Store authentication info in Flask's g object for use in query execution
    g.username = username
    g.password = password
    return True

def chdb_query_with_errmsg(query, format):
    try:
        new_stderr = tempfile.TemporaryFile()
        old_stderr_fd = os.dup(2)
        os.dup2(new_stderr.fileno(), 2)

        # Get authentication info from Flask's g object
        username = getattr(g, "username", None)
        password = getattr(g, "password", None)
        
        # Execute query with proper session management
        result = execute_query_with_session(query, format, username, password)

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
        return result, 200
    if len(result) > 0:
        print("warning:", errmsg)
        return result, 200
    return errmsg, 400

@app.route('/', methods=["POST"])
@auth.login_required
def play():
    query = request.args.get('query', default=None, type=str)
    body = request.get_data() or None
    format = request.args.get('default_format', default="TSV", type=str)
    database = request.args.get('database', default="", type=str)

    if query is None:
        query = b""
    else:
        query = query.encode('utf-8')

    if body is not None:
        # temporary hack to flatten multilines. to be replaced with raw `--file` input
        data = f""
        request_lines = body.decode('utf-8').strip().splitlines(True)
        for line in request_lines:
           data += " " + line.strip()
        body = data.encode('utf-8')
        query = query + " ".encode('utf-8') + body

    if not query:
        return "Error: no query parameter provided", 400

    if database:
        database = f"USE {database}; ".encode()
        query = database + query

    result, errmsg = chdb_query_with_errmsg(query.strip(), format)
    if len(errmsg) == 0:
        return result, 200
    if len(result) > 0:
        print("warning:", errmsg)
        return result, 200
    return errmsg, 400

@app.route('/play', methods=["GET"])
def handle_play():
    return app.send_static_file('index.html')

@app.route('/ping', methods=["GET"])
def handle_ping():
    return Response("Ok\n", mimetype='text/plain')

@app.errorhandler(404)
def handle_404(e):
    return app.send_static_file('index.html')

def start_native_server():
    """Start the native protocol server in a separate thread"""
    global native_server
    native_server = NativeProtocolServer(host=host, port=native_port)
    native_server.start()

def stop_native_server():
    """Stop the native protocol server"""
    global native_server
    if native_server:
        native_server.stop()

def cleanup_sessions():
    """Clean up all persistent sessions"""
    global session_manager
    with session_lock:
        for auth_key, session in session_manager.items():
            try:
                session.close()
                print(f"🔧 Closed session for {auth_key}")
            except Exception as e:
                print(f"⚠️  Error closing session for {auth_key}: {e}")
        session_manager.clear()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nShutting down servers...")
    stop_native_server()
    cleanup_sessions()
    print("Exiting...")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting CowsDB server...")
    print(f"HTTP API: http://{host}:{port}")
    print(f"Native protocol: {host}:{native_port}")
    
    # Start native protocol server in background thread
    native_thread = threading.Thread(target=start_native_server, daemon=True)
    native_thread.start()
    
    # Start Flask app
    app.run(host=host, port=port, debug=False) 