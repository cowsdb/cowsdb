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
import zlib
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
    # Additional packet types that might be sent by the client
    CLIENT_INFO = 6
    SETTINGS = 7
    EXTENSION = 8

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

# Additional protocol constants that might be missing
DBMS_MIN_REVISION_WITH_CLIENT_INFO = 54032
DBMS_MIN_REVISION_WITH_QUOTA_KEY_IN_CLIENT_INFO = 54060
DBMS_MIN_REVISION_WITH_SETTINGS_SERIALIZED_AS_STRINGS = 54429
DBMS_MIN_REVISION_WITH_INTERSERVER_SECRET = 54441
DBMS_MIN_PROTOCOL_VERSION_WITH_PARAMETERS = 54459
DBMS_MIN_PROTOCOL_VERSION_WITH_INITIAL_QUERY_START_TIME = 54449

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
        
        # Check if session is valid
        if session is None:
            print(f"❌ Session is None for user {username}")
            return b""
        
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
        import traceback
        traceback.print_exc()
        return b""  # Return empty bytes for errors

class NativeProtocolServer:
    def __init__(self, host='0.0.0.0', port=9000):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.active_connections = set()  # Track active connections
        self.connection_lock = threading.Lock()  # Thread safety for connection tracking
        
    def start(self):
        """Start the native protocol server"""
        print(f"DEBUG: Creating socket for {self.host}:{self.port}")
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Set socket timeout to prevent blocking indefinitely
        self.server_socket.settimeout(1.0)
        print(f"DEBUG: Binding socket to {self.host}:{self.port}")
        self.server_socket.bind((self.host, self.port))
        print(f"DEBUG: Starting to listen on {self.host}:{self.port}")
        self.server_socket.listen(10)  # Increased backlog for better concurrency
        self.running = True
        
        print(f"Native protocol server listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                try:
                    print(f"DEBUG: Waiting for connection on {self.host}:{self.port}")
                    client_socket, address = self.server_socket.accept()
                    print(f"Native connection from {address}")
                    
                    # Set socket options for better performance
                    client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    client_socket.settimeout(30.0)  # 30 second timeout for client operations
                    
                    # Track the connection
                    with self.connection_lock:
                        self.active_connections.add(client_socket)
                    
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    # Timeout is expected, continue listening
                    continue
                except Exception as e:
                    if self.running:  # Only log if we're still supposed to be running
                        print(f"Native server error: {e}")
                        import traceback
                        traceback.print_exc()
                    
        except Exception as e:
            print(f"Native server error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.stop()
    
    def stop(self):
        """Stop the server"""
        self.running = False
        
        # Close all active connections
        with self.connection_lock:
            for client_socket in self.active_connections:
                try:
                    client_socket.close()
                except:
                    pass
            self.active_connections.clear()
        
        if self.server_socket:
            self.server_socket.close()
        print("Native protocol server stopped")
    
    def handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle a single client connection"""
        # Create connection-specific state
        connection_state = {
            'handshake_complete': False,
            'client_revision': None,
            'current_user': None,
            'current_password': None
        }
        
        try:
            print(f"DEBUG: New connection from {address}")
            # Initial handshake
            if not self.perform_handshake(client_socket, connection_state):
                print(f"DEBUG: Handshake failed for {address}")
                return
            
            # Main client loop
            while True:
                try:
                    if not self.handle_protocol_packet(client_socket, address, connection_state):
                        print(f"DEBUG: Protocol packet handling failed for {address}")
                        break
                except socket.timeout:
                    print(f"DEBUG: Socket timeout for {address}")
                    break
                except Exception as e:
                    print(f"DEBUG: Error in client loop for {address}: {e}")
                    import traceback
                    traceback.print_exc()
                    break
        except Exception as e:
            print(f"DEBUG: Error in handle_client for {address}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"DEBUG: Closing connection for {address}")
            # Remove from active connections
            with self.connection_lock:
                if client_socket in self.active_connections:
                    self.active_connections.remove(client_socket)
            client_socket.close()
    
    def perform_handshake(self, client_socket: socket.socket, connection_state: dict) -> bool:
        """Perform protocol handshake with client"""
        try:
            # Read client hello
            packet_type = self.read_varint(client_socket)
            if packet_type != ClientPacketTypes.HELLO:
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
            connection_state['current_user'] = user
            connection_state['current_password'] = password
            connection_state['client_revision'] = client_revision
            
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
            
            # Mark handshake as complete for this connection
            connection_state['handshake_complete'] = True
            
            return True
            
        except Exception as e:
            print(f"DEBUG: Handshake error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def handle_protocol_packet(self, client_socket: socket.socket, address: tuple, connection_state: dict):
        """Handle protocol packets more robustly"""
        try:
            # Read packet type
            packet_type = self.read_varint(client_socket)
            
            if packet_type == ClientPacketTypes.HELLO:
                # Only send HELLO response during initial handshake
                # After handshake, HELLO packets should be ignored or handled differently
                if not connection_state['handshake_complete']:
                    # Send HELLO response
                    self.write_varint(ServerPacketTypes.HELLO, client_socket)
                    self.write_binary_str(DBMS_NAME, client_socket)
                    self.write_varint(DBMS_VERSION_MAJOR, client_socket)
                    self.write_varint(DBMS_VERSION_MINOR, client_socket)
                    self.write_varint(DBMS_REVISION, client_socket)
                    connection_state['handshake_complete'] = True
                return True
            elif packet_type == ClientPacketTypes.QUERY:
                return self.handle_query(client_socket, address, connection_state)
            elif packet_type == ClientPacketTypes.DATA:
                return self.handle_data(client_socket, address, connection_state)
            elif packet_type == ClientPacketTypes.PING:
                return self.handle_ping(client_socket)
            elif packet_type == ClientPacketTypes.CANCEL:
                return self.handle_cancel(client_socket)
            else:
                print(f"DEBUG: Unknown packet type: {packet_type}")
                return False
        except Exception as e:
            print(f"DEBUG: Error handling protocol packet: {e}")
            return False
    
    def handle_query(self, client_socket: socket.socket, address: tuple, connection_state: dict):
        """Handle a QUERY packet from the client"""
        try:
            # Read query ID
            query_id = self.read_binary_str(client_socket)
            
            # Read client info if revision supports it
            if connection_state['client_revision'] >= DBMS_MIN_REVISION_WITH_CLIENT_INFO:
                # Skip client info for now - read the structure properly
                query_kind = self.read_uint8(client_socket)
                if query_kind != 0:  # Not empty
                    initial_user = self.read_binary_str(client_socket)
                    initial_query_id = self.read_binary_str(client_socket)
                    initial_address = self.read_binary_str(client_socket)
                    
                    # Read initial query start time if supported
                    if connection_state['client_revision'] >= DBMS_MIN_PROTOCOL_VERSION_WITH_INITIAL_QUERY_START_TIME:
                        initial_query_start_time = self.read_uint64(client_socket)
                    
                    interface = self.read_uint8(client_socket)
                    os_user = self.read_binary_str(client_socket)
                    client_hostname = self.read_binary_str(client_socket)
                    client_name = self.read_binary_str(client_socket)
                    client_version_major = self.read_varint(client_socket)
                    client_version_minor = self.read_varint(client_socket)
                    client_revision = self.read_varint(client_socket)
                    
                    # Read quota key if supported
                    if client_revision >= DBMS_MIN_REVISION_WITH_QUOTA_KEY_IN_CLIENT_INFO:
                        quota_key = self.read_binary_str(client_socket)
                    
                    # Read distributed depth if supported
                    if client_revision >= 54448:  # DBMS_MIN_PROTOCOL_VERSION_WITH_DISTRIBUTED_DEPTH:
                        distributed_depth = self.read_varint(client_socket)
            
            # Read settings
            settings_as_strings = connection_state['client_revision'] >= DBMS_MIN_REVISION_WITH_SETTINGS_SERIALIZED_AS_STRINGS
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
            
            # Read inter-server secret if revision supports it
            if connection_state['client_revision'] >= DBMS_MIN_REVISION_WITH_INTERSERVER_SECRET:
                inter_server_secret = self.read_binary_str(client_socket)
            
            # Read query processing stage
            query_stage = self.read_varint(client_socket)
            
            # Read compression flag
            compression = self.read_varint(client_socket)
            
            # Read query text based on compression flag
            if compression == 0:
                # No compression
                query = self.read_binary_str(client_socket)
            elif compression == 1:
                # Compressed query
                query = self.read_compressed_binary_str(client_socket)
            else:
                # Unknown compression type (compression == 2)
                # The client seems to send an empty compressed string first, then the actual query
                empty_compressed = self.read_compressed_binary_str(client_socket)
                # Now read the actual query as a regular binary string
                query = self.read_binary_str(client_socket)
            
            print(f"DEBUG: Executing query: {query}")
            
            # Read parameters if revision supports it
            if connection_state['client_revision'] >= DBMS_MIN_PROTOCOL_VERSION_WITH_PARAMETERS:
                # Read custom settings (parameters)
                while True:
                    param_name = self.read_binary_str(client_socket)
                    if not param_name:  # End of parameters
                        break
                    flags = self.read_uint8(client_socket)
                    param_value = self.read_binary_str(client_socket)
            
            # Execute the query
            try:
                print(f"DEBUG: About to execute query: '{query}'")
                # Extract FORMAT from query if present, otherwise use NATIVE
                format_name = "NATIVE"  # Default format for native protocol
                query_for_chdb = query
                
                # Check if query contains FORMAT clause
                if "FORMAT" in query.upper():
                    # Extract format from query like "SELECT 1 FORMAT JSON"
                    parts = query.upper().split("FORMAT")
                    if len(parts) > 1:
                        format_name = parts[1].strip()
                        # Remove format from query for chdb
                        query_for_chdb = parts[0].strip()
                    else:
                        query_for_chdb = query
                else:
                    # Add NATIVE format for SELECT queries
                    if query.strip().upper().startswith('SELECT'):
                        query_for_chdb = f"{query} FORMAT {format_name}"
                
                print(f"DEBUG: Final query for chdb: '{query_for_chdb}'")
                result = execute_query_with_session(query_for_chdb, format_name, connection_state['current_user'], connection_state['current_password'])
                
                print(f"DEBUG: Query result: {len(result) if result else 0} bytes")
                if result:
                    print(f"DEBUG: Raw result bytes: {result[:50]}...")  # Show first 50 bytes
                    print(f"DEBUG: Full result bytes: {list(result)}")  # Show all bytes as list
                
                if result and len(result) > 0 and query.strip().upper().startswith('SELECT'):
                    # Send DATA packet with results
                    self.write_varint(ServerPacketTypes.DATA, client_socket)
                    # Send empty table name as binary string (required by protocol)
                    self.write_binary_str("", client_socket)
                    
                    # Send BlockInfo structure (required by protocol)
                    # BlockInfo: field_num=1 (is_overflows), field_num=2 (bucket_num), field_num=0 (end marker)
                    self.write_varint(1, client_socket)  # field_num=1
                    self.write_uint8(0, client_socket)   # is_overflows=False
                    self.write_varint(2, client_socket)  # field_num=2
                    self.write_int32(-1, client_socket)  # bucket_num=-1
                    self.write_varint(0, client_socket)  # field_num=0 (end marker)
                    
                    # Parse chdb NATIVE result format
                    # Format: [n_columns, n_rows, column1_name_len, column1_name, column1_type_len, column1_type, column1_data, ...]
                    pos = 0
                    n_columns = result[pos]; pos += 1
                    n_rows = result[pos]; pos += 1
                    
                    print(f"DEBUG: Parsing {n_columns} columns, {n_rows} rows")
                    
                    columns = []
                    for col_idx in range(n_columns):
                        # Read column name
                        col_name_len = result[pos]; pos += 1
                        col_name = result[pos:pos+col_name_len].decode('ascii'); pos += col_name_len
                        
                        # Read column type
                        col_type_len = result[pos]; pos += 1
                        col_type = result[pos:pos+col_type_len].decode('ascii'); pos += col_type_len
                        
                        print(f"DEBUG: Column {col_idx}: {col_name} ({col_type})")
                        
                        # Read column data
                        if col_type == 'String':
                            # For String columns, read the string data
                            if n_rows > 1:
                                # Multiple rows: each string is length-prefixed
                                col_data = result[pos:]; pos = len(result)  # Read all remaining data
                            else:
                                # Single row: read the string data
                                str_len = result[pos]; pos += 1
                                col_data = result[pos:pos+str_len]; pos += str_len
                        else:
                            # For numeric types, read fixed-size data
                            if col_type == 'UInt8':
                                data_size = 1
                            elif col_type == 'UInt32':
                                data_size = 4
                            elif col_type == 'UInt64':
                                data_size = 8
                            elif col_type == 'Float64':
                                data_size = 8
                            else:
                                data_size = 1  # Default
                            
                            col_data = result[pos:pos + (n_rows * data_size)]; pos += n_rows * data_size
                        
                        columns.append((col_name, col_type, col_data))
                        print(f"DEBUG: Column {col_idx} data: {list(col_data)}")
                    
                    # Send block data in the format expected by clickhouse-driver
                    self.write_varint(n_columns, client_socket)  # n_columns
                    self.write_varint(n_rows, client_socket)  # n_rows
                    
                    # Send each column's metadata and data
                    for col_name, col_type, col_data in columns:
                        # Send column name
                        self.write_binary_str(col_name, client_socket)
                        
                        # Send column type
                        self.write_binary_str(col_type, client_socket)
                        
                        # Send custom serialization flag (0) - required for revision >= 54454
                        self.write_uint8(0, client_socket)
                        
                        # Send the actual data in the format expected by clickhouse-driver
                        if col_type == 'String':
                            # For String columns, send each string with its length as varint
                            if n_rows > 1:
                                # Parse multiple strings from the data
                                string_pos = 0
                                for row_idx in range(n_rows):
                                    if string_pos < len(col_data):
                                        str_len = col_data[string_pos]; string_pos += 1
                                        if string_pos + str_len <= len(col_data):
                                            string_val = col_data[string_pos:string_pos + str_len]
                                            # Send string length as varint, then string data
                                            self.write_varint(str_len, client_socket)
                                            client_socket.send(string_val)
                                            string_pos += str_len
                            else:
                                # Single row: send the string length as varint, then the string data
                                self.write_varint(len(col_data), client_socket)
                                client_socket.send(col_data)
                        else:
                            # For numeric types, send the data as-is
                            client_socket.send(col_data)
                else:
                    # For non-SELECT queries (DDL, DML), don't send any data block
                    # Just send END_OF_STREAM directly
                    print(f"DEBUG: Non-SELECT query, sending END_OF_STREAM directly")
                    pass
                
                # Send END_OF_STREAM packet
                self.write_varint(ServerPacketTypes.END_OF_STREAM, client_socket)
                
            except Exception as e:
                # Send EXCEPTION packet
                self.write_varint(ServerPacketTypes.EXCEPTION, client_socket)
                self.write_binary_str(str(e), client_socket)
                
        except Exception as e:
            print(f"DEBUG: Error in handle_query: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True
    
    def handle_data(self, client_socket: socket.socket, address: tuple, connection_state: dict):
        """Handle a DATA packet from the client"""
        try:
            # Read table name
            table_name = self.read_binary_str(client_socket)
            print(f"DEBUG: DATA packet for table: {table_name}")
            
            # For now, just acknowledge the DATA packet
            # This is a simplified approach to get basic functionality working
            print(f"DEBUG: Acknowledging DATA packet for table: {table_name}")
            
            # Send END_OF_STREAM to acknowledge
            self.write_varint(ServerPacketTypes.END_OF_STREAM, client_socket)
            return True
            
        except Exception as e:
            print(f"DEBUG: Error in handle_data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def handle_ping(self, client_socket: socket.socket):
        """Handle ping from client"""
        print(f"DEBUG: Sending PONG response")
        self.write_varint(ServerPacketTypes.PONG, client_socket)
        print(f"DEBUG: PONG sent successfully")
        return True
    
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
        raw_bytes = []
        while True:
            data = sock.recv(1)
            if not data:
                raise ConnectionError("Connection closed by peer")
            byte = data[0]
            raw_bytes.append(byte)
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        print(f"DEBUG: read_varint: bytes={raw_bytes} value={result}")
        return result
    
    def write_varint(self, value: int, sock: socket.socket):
        """Write a variable-length integer in the exact format expected by clickhouse-driver (little-endian)"""
        original_value = value
        if value < 0:
            # Handle negative numbers - convert to unsigned
            value = (1 << 64) + value
        
        bytes_to_send = []
        while value >= 0x80:
            bytes_to_send.append((value & 0x7F) | 0x80)
            value >>= 7
        bytes_to_send.append(value & 0x7F)
        
        sock.send(bytes(bytes_to_send))
    
    def write_uint64(self, value: int, sock: socket.socket):
        """Write a 64-bit unsigned integer in little-endian format"""
        sock.send(struct.pack('<Q', value))
    
    def write_uint8(self, value: int, sock: socket.socket):
        """Write an 8-bit unsigned integer in little-endian format"""
        sock.send(struct.pack('<B', value))
    
    def write_int32(self, value: int, sock: socket.socket):
        """Write a 32-bit signed integer in little-endian format"""
        sock.send(struct.pack('<i', value))
    
    def read_binary_str(self, sock: socket.socket) -> str:
        """Read a binary string"""
        length = self.read_varint(sock)
        print(f"DEBUG: read_binary_str: length={length}")
        if length == 0:
            return ""
        data = sock.recv(length)
        if len(data) != length:
            raise ConnectionError("Connection closed by peer")
        result = data.decode('utf-8')
        print(f"DEBUG: read_binary_str: result='{result}'")
        return result
    
    def read_compressed_binary_str(self, sock: socket.socket) -> str:
        """Read a compressed binary string"""
        compressed_length = self.read_varint(sock)
        print(f"DEBUG: read_compressed_binary_str: compressed_length={compressed_length}")
        if compressed_length == 0:
            return ""
        
        # Read compressed data
        compressed_data = sock.recv(compressed_length)
        if len(compressed_data) != compressed_length:
            raise ConnectionError("Connection closed by peer")
        
        # Decompress the data
        try:
            decompressed_data = zlib.decompress(compressed_data)
            result = decompressed_data.decode('utf-8')
            print(f"DEBUG: read_compressed_binary_str: result='{result}'")
            return result
        except Exception as e:
            print(f"DEBUG: Error decompressing data: {e}")
            # If decompression fails, try to read as uncompressed
            print(f"DEBUG: Trying to read as uncompressed string")
            return compressed_data.decode('utf-8', errors='ignore')
    
    def write_binary_str(self, value: str, sock: socket.socket):
        """Write a binary string in the format expected by clickhouse-driver"""
        if isinstance(value, str):
            value = value.encode('utf-8')
        # Write the length as a varint
        self.write_varint(len(value), sock)
        # Write the string data
        if len(value) > 0:
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
    print("DEBUG: Starting native server thread...")
    native_server = NativeProtocolServer(host=host, port=native_port)
    print("DEBUG: Native server created, starting...")
    native_server.start()
    print("DEBUG: Native server started successfully")

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