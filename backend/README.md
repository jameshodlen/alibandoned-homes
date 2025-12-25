# Abandoned Homes Prediction API

A comprehensive FastAPI backend for predicting and cataloging abandoned homes, with extensive educational documentation for learning web API development.

## 🎓 Educational Focus

This codebase is designed to teach backend development concepts:

- **REST API Design**: HTTP methods, status codes, versioning
- **Authentication**: API keys, security best practices
- **Database**: SQLAlchemy ORM, async operations, spatial data
- **Validation**: Pydantic schemas, custom validators
- **File Uploads**: Multipart forms, security, storage
- **Background Tasks**: Long-running operations, job queues
- **Testing**: pytest, fixtures, integration tests
- **Rate Limiting**: Abuse prevention, fair usage

Every file contains extensive inline comments explaining concepts, best practices, and common pitfalls.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with PostGIS extension
- (Optional) Docker for containerized database

### Installation

1. **Clone repository and navigate to backend:**

   ```bash
   cd backend
   ```

2. **Create virtual environment:**

   ```bash
   python -m venv venv

   # Activate
   # Windows:
   venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up database:**

   ```bash
   # Using Docker (recommended for development)
   docker run -d \
     --name postgis \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=abandoned_homes \
     -p 5432:5432 \
     postgis/postgis:15-3.3
   ```

5. **Set environment variables:**

   ```bash
   # Create .env file
   echo 'DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/abandoned_homes' > .env
   echo 'API_KEY=your-secure-random-key-here' >> .env
   ```

6. **Run database migrations:**

   ```bash
   alembic upgrade head
   ```

7. **Start the server:**

   ```bash
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

8. **Access the API:**
   - API: http://localhost:8000
   - Interactive docs: http://localhost:8000/docs
   - Alternative docs: http://localhost:8000/redoc

## 📚 Documentation

- **[API Usage Guide](../brain/5e61d6a2-1af7-4f2c-99ca-7f74f5bec31e/API_GUIDE.md)**: Complete API reference with examples
- **[Interactive Docs](http://localhost:8000/docs)**: Swagger UI for testing endpoints
- **Inline Documentation**: Every file has extensive educational comments

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_api.py -v

# Run with coverage
pytest tests/ --cov=api --cov-report=html
```

View coverage report:

```bash
open htmlcov/index.html
```

## 📁 Project Structure

```
backend/
├── api/
│   ├── main.py              # FastAPI app setup, CORS, middleware
│   ├── auth.py              # API key authentication
│   ├── schemas.py           # Pydantic request/response schemas
│   └── routes/
│       ├── locations.py     # CRUD for locations
│       ├── predictions.py   # ML predictions (background tasks)
│       ├── photos.py        # Photo upload/download
│       └── admin.py         # Admin endpoints
├── database/
│   ├── base.py              # Database connection, session management
│   └── models.py            # SQLAlchemy models (Location, Photo, Prediction)
├── tests/
│   └── test_api.py          # API integration tests
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

## 🔑 Authentication

All endpoints (except `/health`) require an API key in the request header:

```bash
curl -H "X-API-Key: your-api-key" \
     http://localhost:8000/api/v1/locations
```

Generate a secure API key:

```python
import secrets
print(secrets.token_urlsafe(32))
```

## 📖 API Examples

### Create a Location

```bash
curl -X POST http://localhost:8000/api/v1/locations/ \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 42.3314,
    "longitude": -83.0458,
    "confirmed": false,
    "condition": "partial_collapse",
    "accessibility": "moderate",
    "notes": "Boarded windows"
  }'
```

### List Locations

```bash
# Get first 20 locations
curl "http://localhost:8000/api/v1/locations/?limit=20" \
  -H "X-API-Key: your-key"

# Filter by bounding box (Detroit area)
curl "http://localhost:8000/api/v1/locations/?bbox=-83.3,42.2,-83.0,42.4" \
  -H "X-API-Key: your-key"
```

### Start Area Prediction

```bash
curl -X POST http://localhost:8000/api/v1/predictions/predict-area \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "center_lat": 42.3314,
    "center_lon": -83.0458,
    "radius_km": 5.0,
    "threshold": 0.7
  }'
```

See the [API Guide](../brain/5e61d6a2-1af7-4f2c-99ca-7f74f5bec31e/API_GUIDE.md) for complete documentation.

## 🔐 Security Best Practices

- ✅ Always use HTTPS in production
- ✅ Store API keys in environment variables (never in code)
- ✅ Rotate API keys every 90 days
- ✅ Validate all input data (Pydantic does this automatically)
- ✅ Use rate limiting to prevent abuse
- ✅ Strip GPS EXIF data from uploaded photos
- ✅ Implement proper CORS policies
- ✅ Log all authentication failures

## 📊 Database Schema

### Key Tables

- **locations**: Abandoned home locations (PostGIS POINT geometry)
- **photos**: Images associated with locations
- **predictions**: ML model predictions

### Spatial Queries

PostGIS enables powerful geospatial queries:

```python
# Find locations within 5km of a point
from sqlalchemy import func

point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
query = select(Location).where(
    func.ST_DWithin(Location.coordinates, point, 5000)
)
```

## 🎯 Learning Path

If you're new to backend development, study the files in this order:

1. **database/base.py**: Learn about async SQLAlchemy, connection pools, sessions
2. **database/models.py**: Understand ORM models, relationships, spatial data
3. **api/schemas.py**: Master Pydantic validation, request/response schemas
4. **api/auth.py**: Learn authentication strategies, security best practices
5. **api/routes/locations.py**: Study REST API design, CRUD operations
6. **api/routes/predictions.py**: Understand background tasks, long-running operations
7. **api/routes/photos.py**: Learn file upload handling, security
8. **api/main.py**: See how everything comes together
9. **tests/test_api.py**: Master API testing with pytest

Each file contains extensive educational comments explaining:

- What the code does
- Why it's designed that way
- Common pitfalls to avoid
- Best practices
- Real-world examples

## 🛠 Development

### Running with Auto-Reload

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Server automatically restarts when code changes.

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new field"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Logging

All requests are logged. Check server output for:

- Request method and path
- Response status code
- Response time
- Errors and stack traces

## 🐛 Troubleshooting

### "Connection refused" error

- Check PostgreSQL is running: `docker ps`
- Verify DATABASE_URL in .env file
- Test connection: `psql -h localhost -U postgres -d abandoned_homes`

### "Invalid API key"

- Check `X-API-Key` header is set correctly
- Verify API_KEY in .env matches request
- No extra spaces in header value

### "ModuleNotFoundError"

- Activate virtual environment
- Install dependencies: `pip install -r requirements.txt`

### "Table doesn't exist"

- Run migrations: `alembic upgrade head`
- Check database connection

## 📝 License

MIT License - feel free to use for learning and projects.

## 🤝 Contributing

This is an educational project. Contributions that improve the learning experience are welcome:

- Additional inline documentation
- More test examples
- Better error messages
- Tutorial improvements

## 📬 Support

- Open an issue for bugs
- Check `/docs` endpoint for interactive API documentation
- Review inline comments in source code
- See API_GUIDE.md for complete API reference

---

**Happy Learning! 🚀**
