# Load Testing Automation

This service provides automated load testing capabilities for the Flask EC application, generating continuous load to produce monitoring data in New Relic.

## Features

- **Automated Load Generation**: Configurable concurrent users and test duration
- **Random Endpoint Selection**: Weighted random selection of performance problem endpoints
- **Web Management UI**: Simple dashboard for configuration and monitoring
- **Configuration Management**: JSON-based configuration with validation
- **Docker Integration**: Runs as an independent container alongside the main application

## Quick Start

The load tester is automatically included in the docker-compose setup:

```bash
# Start all services including load tester
docker-compose up -d

# Access the load tester dashboard
open http://localhost:8080
```

## Configuration

The service uses environment variables and JSON configuration files:

### Environment Variables

- `LOAD_TESTER_TARGET_APP_URL`: Target Flask application URL (default: http://web:5000)
- `LOAD_TESTER_LOG_LEVEL`: Logging level (default: INFO)

### Configuration File

Configuration is stored in `data/config.json` with the following structure:

```json
{
  "load_test": {
    "concurrent_users": 10,
    "duration_minutes": 30,
    "request_interval_min": 1.0,
    "request_interval_max": 5.0,
    "max_errors_per_minute": 100,
    "enable_logging": true
  },
  "endpoints": {
    "/performance/slow": {"weight": 1.0, "enabled": true},
    "/performance/n-plus-one": {"weight": 1.0, "enabled": true},
    "/performance/slow-query": {"weight": 1.0, "enabled": true},
    "/performance/js-errors": {"weight": 1.0, "enabled": true},
    "/performance/bad-vitals": {"weight": 1.0, "enabled": true}
  },
  "safety": {
    "max_concurrent_users": 50,
    "max_duration_minutes": 120,
    "emergency_stop_enabled": true
  }
}
```

## API Endpoints

- `GET /`: Dashboard UI
- `GET /health`: Health check
- `GET /api/config`: Get current configuration
- `POST /api/config`: Update configuration
- `GET /api/status`: Get load testing status

## Development

### Local Development

```bash
cd load-tester
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### Building the Container

```bash
docker build -t load-tester ./load-tester
```

## Architecture

The load tester runs as a completely independent service that communicates with the target Flask application only through HTTP requests. This ensures:

- **Zero Impact**: No changes required to the existing application
- **Isolation**: Independent lifecycle and resource management
- **Scalability**: Can be deployed and scaled independently

## Next Steps

This basic structure provides the foundation for:

1. Endpoint configuration and random selection (Task 2)
2. Async HTTP load generation (Task 3)
3. Web management UI (Task 4)
4. Advanced configuration management (Task 5)
5. Error handling and safety features (Task 6)