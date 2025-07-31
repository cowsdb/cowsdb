<img src="https://github.com/user-attachments/assets/685cc433-a5bb-45a4-bbd2-4f132f6dec44" width=140><img src="https://github.com/user-attachments/assets/685cc433-a5bb-45a4-bbd2-4f132f6dec44" width=100><img src="https://github.com/user-attachments/assets/685cc433-a5bb-45a4-bbd2-4f132f6dec44" width=70><img src="https://github.com/user-attachments/assets/685cc433-a5bb-45a4-bbd2-4f132f6dec44" width=40>

# CowsDB
[![CowsDB SQL Bench](https://github.com/cowsdb/cowsdb/actions/workflows/test.yml/badge.svg)](https://github.com/cowsdb/cowsdb/actions/workflows/test.yml)

> CowsDB prentends to be ClickHouse and can be used with any ClickHouse client for serverless ops

## ✨ Features

- **🔌 ClickHouse HTTP API Compatibility** - Full HTTP API support on port 8123
- **⚡ Native Protocol Support** - Binary protocol support on port 9000
- **📊 Multiple Output Formats** - TSV, JSON, CSV, and Native binary formats

<br>

## 🚀 Quick Start
```
docker run --rm -p 8123:8123 -p 9000:9000 ghcr.io/cowsdb/cowsdb:latest
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

## 📖 Usage

### HTTP API (Port 8123)

#### Basic Query
```bash
curl -G --data-urlencode "query=SELECT version(), now()" http://test:test@localhost:8123
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

### Environment Setup
```bash
# Production environment variables
export HOST=0.0.0.0
export PORT=8123
export NATIVE_PORT=9000

# Start with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8123 main:app
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## 📄 License

CowsDB is licensed under the AGPLv3 license and is NOT affiliated in any way with ClickHouse Inc.


