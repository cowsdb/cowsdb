#!/usr/bin/env python3
"""
CowsDB Comprehensive Test Suite
Tests both HTTP API and Native Protocol functionality
"""

import os
import sys
import time
import socket
import struct
import threading
import subprocess
import requests
from typing import Optional

def read_varint(sock):
    """Read a variable-length integer"""
    result = 0
    shift = 0
    while True:
        byte = sock.recv(1)[0]
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result

def write_varint(value, sock):
    """Write a variable-length integer"""
    while value >= 0x80:
        sock.send(bytes([(value & 0x7F) | 0x80]))
        value >>= 7
    sock.send(bytes([value]))

def read_binary_str(sock):
    """Read a binary string"""
    length = read_varint(sock)
    if length == 0:
        return ""
    return sock.recv(length).decode('utf-8')

def write_binary_str(value, sock):
    """Write a binary string"""
    if isinstance(value, str):
        value = value.encode('utf-8')
    write_varint(len(value), sock)
    sock.send(value)

class CowsDBTestSuite:
    def __init__(self, host='localhost', http_port=8123, native_port=9000):
        self.host = host
        self.http_port = http_port
        self.native_port = native_port
        self.server_process = None
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """Log a test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if message:
            print(f"   {message}")
        self.test_results.append({
            'name': test_name,
            'success': success,
            'message': message
        })
        
    def start_server(self) -> bool:
        """Start the CowsDB server"""
        try:
            print("🚀 Starting CowsDB server...")
            self.server_process = subprocess.Popen(
                [sys.executable, 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            for i in range(10):
                try:
                    response = requests.get(f"http://{self.host}:{self.http_port}/ping", timeout=1)
                    if response.status_code == 200:
                        print("✅ Server started successfully")
                        return True
                except:
                    pass
                time.sleep(1)
            
            print("❌ Server failed to start")
            return False
            
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            return False
    
    def stop_server(self):
        """Stop the CowsDB server"""
        if self.server_process:
            print("🛑 Stopping server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            print("✅ Server stopped")
    
    def test_http_basic(self):
        """Test basic HTTP API functionality"""
        try:
            # Test ping
            response = requests.get(f"http://{self.host}:{self.http_port}/ping")
            if response.status_code == 200 and response.text.strip() == "Ok":
                self.log_test("HTTP Ping", True)
            else:
                self.log_test("HTTP Ping", False, f"Expected 'Ok', got '{response.text}'")
                return False
            
            # Test basic query
            response = requests.get(
                f"http://{self.host}:{self.http_port}/",
                params={'query': 'SELECT 1 as num'},
                auth=('test', 'test')
            )
            if response.status_code == 200 and '1' in response.text:
                self.log_test("HTTP Basic Query", True)
            else:
                self.log_test("HTTP Basic Query", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
            
            return True
            
        except Exception as e:
            self.log_test("HTTP Basic", False, str(e))
            return False
    
    def test_http_data_types(self):
        """Test HTTP API with different data types"""
        test_queries = [
            ("SELECT 1 as num", "Integer"),
            ("SELECT 'hello' as str", "String"),
            ("SELECT 1.5 as float", "Float"),
            ("SELECT now() as datetime", "DateTime"),
            ("SELECT version() as version", "Function"),
            ("SELECT 1 as num, 'test' as str, 3.14 as pi", "Multiple columns"),
        ]
        
        for query, description in test_queries:
            try:
                response = requests.get(
                    f"http://{self.host}:{self.http_port}/",
                    params={'query': query},
                    auth=('test', 'test')
                )
                if response.status_code == 200:
                    self.log_test(f"HTTP {description}", True)
                else:
                    self.log_test(f"HTTP {description}", False, f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(f"HTTP {description}", False, str(e))
    
    def test_http_formats(self):
        """Test HTTP API with different output formats"""
        formats = ['TSV', 'JSON', 'CSV']
        
        for fmt in formats:
            try:
                response = requests.get(
                    f"http://{self.host}:{self.http_port}/",
                    params={'query': 'SELECT 1 as num', 'format': fmt},
                    auth=('test', 'test')
                )
                if response.status_code == 200:
                    self.log_test(f"HTTP Format {fmt}", True)
                else:
                    self.log_test(f"HTTP Format {fmt}", False, f"Status: {response.status_code}")
            except Exception as e:
                self.log_test(f"HTTP Format {fmt}", False, str(e))
    
    def test_native_handshake(self):
        """Test native protocol handshake"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.native_port))
            
            # Send client hello
            write_varint(0, sock)  # HELLO packet
            write_binary_str("ClickHouse python-driver", sock)
            write_varint(20, sock)  # version major
            write_varint(10, sock)  # version minor
            write_varint(54468, sock)  # revision
            write_binary_str("default", sock)  # database
            write_binary_str("default", sock)  # user
            write_binary_str("", sock)  # password
            
            # Read server hello
            packet_type = read_varint(sock)
            if packet_type == 0:  # HELLO
                server_name = read_binary_str(sock)
                version_major = read_varint(sock)
                version_minor = read_varint(sock)
                revision = read_varint(sock)
                
                if server_name == "CowsDB":
                    self.log_test("Native Handshake", True)
                    sock.close()
                    return True
                else:
                    self.log_test("Native Handshake", False, f"Expected 'CowsDB', got '{server_name}'")
                    sock.close()
                    return False
            else:
                self.log_test("Native Handshake", False, f"Expected HELLO packet, got {packet_type}")
                sock.close()
                return False
                
        except Exception as e:
            self.log_test("Native Handshake", False, str(e))
            return False
    
    def test_native_query(self, query: str, description: str) -> bool:
        """Test native protocol with a specific query"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.native_port))
            
            # Send client hello
            write_varint(0, sock)  # HELLO packet
            write_binary_str("ClickHouse python-driver", sock)
            write_varint(20, sock)  # version major
            write_varint(10, sock)  # version minor
            write_varint(54468, sock)  # revision
            write_binary_str("default", sock)  # database
            write_binary_str("default", sock)  # user
            write_binary_str("", sock)  # password
            
            # Read server hello
            packet_type = read_varint(sock)
            if packet_type == 0:  # HELLO
                read_binary_str(sock)  # server name
                read_varint(sock)  # version major
                read_varint(sock)  # version minor
                read_varint(sock)  # revision
                read_binary_str(sock)  # timezone
                read_binary_str(sock)  # display name
                read_varint(sock)  # version patch
                read_varint(sock)  # password rules
                sock.recv(8)  # inter-server secret
            
            # Send query
            write_varint(1, sock)  # QUERY packet
            write_binary_str("", sock)  # query_id
            write_varint(0, sock)  # query_kind (empty)
            write_binary_str("", sock)  # end of settings
            write_binary_str("", sock)  # inter-server secret
            write_varint(2, sock)  # COMPLETE stage
            write_varint(0, sock)  # compression
            write_binary_str(query, sock)  # query
            write_binary_str("", sock)  # end of parameters
            
            # Read response
            response_type = read_varint(sock)
            
            if response_type == 1:  # DATA
                table_name = read_binary_str(sock)
                block_info = read_varint(sock)
                
                # Read the data block
                data = sock.recv(1024)
                if len(data) > 0:
                    self.log_test(f"Native {description}", True)
                    sock.close()
                    return True
                else:
                    self.log_test(f"Native {description}", False, "No data received")
                    sock.close()
                    return False
                    
            elif response_type == 2:  # EXCEPTION
                error_msg = read_binary_str(sock)
                self.log_test(f"Native {description}", False, f"Exception: {error_msg}")
                sock.close()
                return False
            else:
                self.log_test(f"Native {description}", False, f"Unexpected response type: {response_type}")
                sock.close()
                return False
                
        except Exception as e:
            self.log_test(f"Native {description}", False, str(e))
            return False
    
    def test_native_data_types(self):
        """Test native protocol with different data types"""
        test_queries = [
            ("SELECT 1 as num", "Integer"),
            ("SELECT 'hello' as str", "String"),
            ("SELECT 1.5 as float", "Float"),
            ("SELECT now() as datetime", "DateTime"),
            ("SELECT version() as version", "Function"),
            ("SELECT 1 as num, 'test' as str, 3.14 as pi", "Multiple columns"),
        ]
        
        for query, description in test_queries:
            self.test_native_query(query, description)
    
    def test_session_management(self):
        """Test session management and authentication"""
        try:
            # Test with different users
            users = [
                ('user1', 'pass1'),
                ('user2', 'pass2'),
                ('', '')  # No authentication
            ]
            
            for username, password in users:
                auth_tuple = (username, password) if username and password else None
                response = requests.get(
                    f"http://{self.host}:{self.http_port}/",
                    params={'query': 'SELECT 1 as num'},
                    auth=auth_tuple
                )
                if response.status_code == 200:
                    self.log_test(f"Session Management ({username or 'anonymous'})", True)
                else:
                    self.log_test(f"Session Management ({username or 'anonymous'})", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            self.log_test("Session Management", False, str(e))
    
    def run_all_tests(self):
        """Run all tests"""
        print("🧪 CowsDB Comprehensive Test Suite")
        print("=" * 50)
        
        # Start server
        if not self.start_server():
            print("❌ Failed to start server, aborting tests")
            return False
        
        try:
            # HTTP API tests
            print("\n🔍 Testing HTTP API...")
            print("-" * 30)
            self.test_http_basic()
            self.test_http_data_types()
            self.test_http_formats()
            self.test_session_management()
            
            # Native protocol tests
            print("\n🔍 Testing Native Protocol...")
            print("-" * 30)
            self.test_native_handshake()
            self.test_native_data_types()
            
            # Summary
            print("\n📊 Test Results Summary")
            print("=" * 50)
            passed = sum(1 for result in self.test_results if result['success'])
            total = len(self.test_results)
            
            print(f"Total tests: {total}")
            print(f"Passed: {passed}")
            print(f"Failed: {total - passed}")
            
            if passed == total:
                print("🎉 All tests passed!")
                return True
            else:
                print("⚠️  Some tests failed")
                return False
                
        finally:
            self.stop_server()

def main():
    """Main test runner"""
    test_suite = CowsDBTestSuite()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 