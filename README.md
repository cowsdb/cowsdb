<img src="https://github.com/user-attachments/assets/685cc433-a5bb-45a4-bbd2-4f132f6dec44" width=140><img src="https://github.com/user-attachments/assets/685cc433-a5bb-45a4-bbd2-4f132f6dec44" width=100><img src="https://github.com/user-attachments/assets/685cc433-a5bb-45a4-bbd2-4f132f6dec44" width=70><img src="https://github.com/user-attachments/assets/685cc433-a5bb-45a4-bbd2-4f132f6dec44" width=40>

# CowsDB

> CowsDB prentends to be ClickHouse and can be used with any ClickHouse client for serverless ops

## ✨ Features

- **🔌 ClickHouse HTTP API Compatibility** - Full HTTP API support on port 8123
- **⚡ Native Protocol Support** - Binary protocol support on port 9000
- **📊 Multiple Output Formats** - TSV, JSON, CSV, and Native binary formats

## 🚀 Quick Start
```
docker run --rm -p 8123:8123 -p 9000:9000 ghcr.io/cowsdb/cowsdb:latest
```

### Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/cowsdb.git
   cd cowsdb
   ```

2. **Set up virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the server:**
   ```bash
   python main.py
   ```

The server will start with:
- **HTTP API**: `http://localhost:8123`
- **Native Protocol**: `localhost:9000`

## 📖 Usage

### HTTP API (Port 8123)

#### Basic Query
```bash
curl -G --data-urlencode "query=SELECT version(), now()" http://test:test@localhost:8123
```

#### Different Output Formats
```bash
# TSV (default)
curl -G --data-urlencode "query=SELECT 1 as num" http://test:test@localhost:8123

# JSON
curl -G --data-urlencode "query=SELECT 1 as num" --data-urlencode "format=JSON" http://test:test@localhost:8123

# CSV
curl -G --data-urlencode "query=SELECT 1 as num" --data-urlencode "format=CSV" http://test:test@localhost:8123
```

#### POST Queries
```bash
curl -X POST --data "SELECT 1 as num, 'hello' as str" http://test:test@localhost:8123
```

#### Ping Endpoint
```bash
curl http://localhost:8123/ping
# Returns: Ok.
```

### Native Protocol (Port 9000)

#### Using clickhouse-driver
```python
from clickhouse_driver import Client

# Connect to CowsDB
client = Client('localhost', port=9000)

# Execute queries
result = client.execute('SELECT version(), now()')
print(result)

# Query with parameters
result = client.execute('SELECT %(num)s as number', {'num': 42})
print(result)
```

#### Using clickhouse-client
```bash
clickhouse-client --host localhost --port 9000 --query "SELECT version(), now()"
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host address |
| `PORT` | `8123` | HTTP API port |
| `NATIVE_PORT` | `9000` | Native protocol port |
| `SESSION_TTL` | `3600` | Session timeout in seconds |

### Example Configuration
```bash
export HOST=0.0.0.0
export PORT=8123
export NATIVE_PORT=9000
export SESSION_TTL=7200
python main.py
```

## 🧪 Testing

### Run the Complete Test Suite
```bash
# From project root
python run_tests.py tests

# Or directly
python test/test_suite.py

# Or using the CI script
bash test/run_tests.sh
```

This will test:
- ✅ HTTP API functionality
- ✅ Native protocol handshake and queries
- ✅ Multiple data types (Integer, String, Float, DateTime)
- ✅ Different output formats (TSV, JSON, CSV)
- ✅ Session management and authentication
- ✅ Error handling

### Individual Tests

#### HTTP API Tests
```bash
# Test basic functionality
curl -G --data-urlencode "query=SELECT 1 as num" http://test:test@localhost:8123

# Test different formats
curl -G --data-urlencode "query=SELECT 1 as num" --data-urlencode "format=JSON" http://test:test@localhost:8123
```

#### Native Protocol Tests
```bash
# Run the demo (includes native protocol tests)
python run_tests.py demo

# Or run the full test suite
python run_tests.py tests
```

## 🏗️ Architecture

### Components

1. **HTTP API Server** (Flask)
   - Handles HTTP requests on port 8123
   - Supports GET/POST queries
   - Multiple output formats
   - Authentication and session management

2. **Native Protocol Server** (Socket-based)
   - Handles ClickHouse native protocol on port 9000
   - Binary protocol implementation
   - Full handshake and query processing
   - Direct chdb integration

3. **Session Management**
   - TTL-based session cache
   - Authentication-based session isolation
   - Automatic cleanup on server shutdown

### Protocol Support

#### HTTP API Features
- ✅ GET/POST query endpoints
- ✅ Multiple output formats (TSV, JSON, CSV)
- ✅ Authentication (Basic Auth)
- ✅ Session management with TTL
- ✅ Error handling and status codes

#### Native Protocol Features
- ✅ ClickHouse native protocol handshake
- ✅ Query execution with chdb
- ✅ Binary data transmission
- ✅ Authentication support
- ✅ Multiple data types
- ✅ Error handling

## 🔒 Security

### Authentication
- **HTTP API**: Basic authentication with username/password
- **Native Protocol**: Username/password authentication
- **Session Isolation**: Each authenticated user gets isolated sessions

### Session Management
- **TTL-based cleanup**: Sessions expire after configurable time
- **Connection limits**: Maximum 100 concurrent sessions
- **Graceful shutdown**: Proper cleanup on server termination

## 🚀 Production Deployment

### Using Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8123 main:app
```

### Using Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8123 9000

CMD ["python", "main.py"]
```

### Environment Setup
```bash
# Production environment variables
export HOST=0.0.0.0
export PORT=8123
export NATIVE_PORT=9000
export SESSION_TTL=3600

# Start with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8123 main:app
```

## 📊 Performance

### Benchmarks
- **HTTP API**: ~1000 queries/second
- **Native Protocol**: ~2000 queries/second
- **Memory Usage**: ~50MB base + session overhead
- **Session TTL**: Configurable (default: 1 hour)

### Optimization Tips
1. **Use Native Protocol** for high-performance applications
2. **Configure appropriate TTL** based on your use case
3. **Monitor session count** to avoid memory issues
4. **Use connection pooling** in client applications

## 🐛 Troubleshooting

### Common Issues

#### Server Won't Start
```bash
# Check if ports are available
netstat -tulpn | grep :8123
netstat -tulpn | grep :9000

# Check dependencies
pip list | grep -E "(flask|chdb|cachetools)"
```

#### Connection Issues
```bash
# Test HTTP API
curl http://localhost:8123/ping

# Test native protocol
python run_tests.py demo
```

#### Authentication Problems
```bash
# Test with authentication
curl -G --data-urlencode "query=SELECT 1" http://test:test@localhost:8123

# Test without authentication (should fail)
curl -G --data-urlencode "query=SELECT 1" http://localhost:8123
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## 📄 License

CowsDB is licensed under the AGPLv3 license and is not affiliated in any way with ClickHouse Inc.


