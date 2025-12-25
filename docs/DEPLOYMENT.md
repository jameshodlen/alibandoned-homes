# API Deployment Guide

Comprehensive guide for deploying the Abandoned Homes Prediction API to production.

## Local Development

### Quick Start

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export API_KEY="dev-key-change-in-production"
export DATABASE_URL="postgresql://user:pass@localhost/abandoned_homes"

# Run with auto-reload
uvicorn api.main:app --reload --port 8000
```

### Database Setup (Docker)

```bash
# Start PostgreSQL with PostGIS
docker run -d \
  --name postgis \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=abandoned_homes \
  -p 5432:5432 \
  postgis/postgis:15-3.3
```

---

## Production Deployment

### Docker Deployment

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create upload directory
RUN mkdir -p uploads/photos

# Run with Gunicorn for production
CMD ["gunicorn", "api.main:app", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8000"]
```

**docker-compose.yml:**

```yaml
version: "3.8"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/abandoned_homes
      - API_KEY=${API_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - uploads:/app/uploads

  db:
    image: postgis/postgis:15-3.3
    environment:
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=abandoned_homes
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
  uploads:
```

### Environment Variables

| Variable          | Required | Description                                 |
| ----------------- | -------- | ------------------------------------------- |
| `API_KEY`         | Yes      | Primary API key for authentication          |
| `JWT_SECRET_KEY`  | Yes      | Secret for JWT token signing                |
| `DATABASE_URL`    | Yes      | PostgreSQL connection string                |
| `CORS_ORIGINS`    | No       | Allowed frontend domains (comma-separated)  |
| `LOG_LEVEL`       | No       | Logging level (info, debug, warning, error) |
| `MAX_UPLOAD_SIZE` | No       | Max file upload size in MB (default: 10)    |

**Generate secure keys:**

```bash
# API Key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# JWT Secret
python -c "import secrets; print(secrets.token_hex(64))"
```

---

## HTTPS/TLS Setup

### Why HTTPS?

- Encrypts data in transit
- Prevents man-in-the-middle attacks
- Required for production APIs

### Using Caddy (Recommended)

**Caddyfile:**

```
api.yourdomain.com {
    reverse_proxy localhost:8000

    # Automatic HTTPS (Let's Encrypt)
    # Caddy handles certificate renewal
}
```

### Using Nginx + Certbot

**nginx.conf:**

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Monitoring & Health Checks

### Health Check Endpoint

```bash
curl http://localhost:8000/health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "service": "abandoned-homes-api"
}
```

### Prometheus Metrics

Add to `main.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

Metrics available at `/metrics`.

### Logging Configuration

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('api.log')
    ]
)
```

---

## Backup Strategy

### Database Backup

```bash
# Daily automated backup
pg_dump -U user abandoned_homes > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -U user -d abandoned_homes < backup_20240115.sql
```

### Automated Backup Script

```bash
#!/bin/bash
BACKUP_DIR=/backups
DATE=$(date +%Y%m%d)

# Database backup
pg_dump -U user abandoned_homes | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Uploads backup
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /app/uploads

# Keep only last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

---

## Scaling

### Horizontal Scaling

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      replicas: 4
    # ...

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - api
```

### Load Balancer Configuration

```nginx
upstream api_servers {
    least_conn;
    server api_1:8000;
    server api_2:8000;
    server api_3:8000;
    server api_4:8000;
}

server {
    location / {
        proxy_pass http://api_servers;
    }
}
```

---

## Security Checklist

- [ ] HTTPS enabled
- [ ] API keys rotated every 90 days
- [ ] Database password is strong
- [ ] Environment variables (not hardcoded)
- [ ] Rate limiting configured
- [ ] CORS restricted to known domains
- [ ] Security headers enabled
- [ ] Logging enabled
- [ ] Backups automated
- [ ] Monitoring configured
- [ ] Dependencies up to date
- [ ] Firewall configured

---

## Troubleshooting

### Common Issues

**Connection Refused**

```bash
# Check if server is running
curl http://localhost:8000/health

# Check logs
docker logs api_container

# Check port binding
netstat -tlnp | grep 8000
```

**Database Connection Failed**

```bash
# Test connection
psql -h localhost -U user -d abandoned_homes

# Check DATABASE_URL format
postgresql://user:password@host:port/database
```

**Permission Denied (uploads)**

```bash
# Fix permissions
chmod -R 755 uploads/
chown -R www-data:www-data uploads/
```
