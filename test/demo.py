#!/usr/bin/env python3
"""
CowsDB Demo Script
Demonstrates both HTTP API and Native Protocol usage
"""

import requests
from clickhouse_driver import Client
import time

def demo_http_api():
    """Demonstrate HTTP API usage"""
    print("🌐 HTTP API Demo")
    print("=" * 30)
    
    base_url = "http://localhost:8123"
    
    # Test ping
    response = requests.get(f"{base_url}/ping")
    print(f"✅ Ping: {response.text.strip()}")
    
    # Test basic query
    response = requests.get(
        f"{base_url}/",
        params={'query': 'SELECT version(), now()'},
        auth=('test', 'test')
    )
    print(f"✅ Version query: {response.text.strip()}")
    
    # Test different formats
    formats = ['TSV', 'JSON', 'CSV']
    for fmt in formats:
        response = requests.get(
            f"{base_url}/",
            params={'query': 'SELECT 1 as num, "hello" as str', 'format': fmt},
            auth=('test', 'test')
        )
        print(f"✅ {fmt} format: {response.text.strip()[:50]}...")

def demo_native_protocol():
    """Demonstrate Native Protocol usage"""
    print("\n⚡ Native Protocol Demo")
    print("=" * 30)
    
    try:
        # Connect to CowsDB
        client = Client('localhost', port=9000)
        
        # Test basic query
        result = client.execute('SELECT version(), now()')
        print(f"✅ Version query: {result}")
        
        # Test different data types
        result = client.execute('SELECT 1 as num, "hello" as str, 3.14 as pi')
        print(f"✅ Data types: {result}")
        
        # Test with parameters
        result = client.execute('SELECT %(num)s as number', {'num': 42})
        print(f"✅ Parameterized query: {result}")
        
    except Exception as e:
        print(f"❌ Native protocol error: {e}")

def main():
    """Main demo function"""
    print("🚀 CowsDB Demo")
    print("=" * 50)
    
    # Wait for server to be ready
    print("⏳ Waiting for server to be ready...")
    for i in range(10):
        try:
            response = requests.get("http://localhost:8123/ping", timeout=1)
            if response.status_code == 200:
                print("✅ Server is ready!")
                break
        except:
            pass
        time.sleep(1)
    else:
        print("❌ Server not ready. Please start the server first:")
        print("   python main.py")
        return
    
    # Run demos
    demo_http_api()
    demo_native_protocol()
    
    print("\n🎉 Demo completed!")

if __name__ == "__main__":
    main() 