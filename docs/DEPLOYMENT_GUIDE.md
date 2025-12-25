# Deployment Guide

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 20GB disk space

## Initial Setup

1. **Clone repository:**

```bash
git clone <your-repo-url>
cd abandoned-homes-finder
```

2. **Configure environment:**

```bash
cp .env.example .env
# Edit .env with your specific values
# Ensure strong passwords for production
```

3. **Generate secrets:**

```bash
# Generate secure API key
openssl rand -hex 32

# Generate JWT secret
openssl rand -hex 32
```

4. **Start services:**

```bash
docker-compose up -d
```

5. **Check status:**

```bash
docker-compose ps
docker-compose logs -f
```

## Accessing the Application

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Database:** localhost:5432 (default user: postgres, db: abandoned_homes)

## Common Operations

### View logs

```bash
# Backend logs
docker-compose logs -f backend

# Frontend logs
docker-compose logs -f frontend

# Database logs
docker-compose logs -f db
```

### Restart service

```bash
docker-compose restart backend
```

### Execute command in container

```bash
# Open shell in backend
docker-compose exec backend /bin/bash

# Run database migration (if using alembic)
docker-compose exec backend python -m alembic upgrade head
```

### Database backup

```bash
# Run backup script
./scripts/backup.sh
```

### Restore from backup

```bash
# Stop app using db
docker-compose stop backend

# Restore data
cat backups/YYYYMMDD_HHMMSS/database.sql | docker-compose exec -T db psql -U postgres abandoned_homes

# Restart app
docker-compose start backend
```

## Updating Application

To deploy new code:

```bash
./scripts/deploy.sh
```

## Troubleshooting

### Container won't start

```bash
# Check exit code and logs
docker-compose ps -a
docker-compose logs <service-name>
```

### Database connection error

- **Check `.env`**: Ensure `DATABASE_URL` matches compose service name (`db`).
- **Check Network**: Ensure both containers are on `app-network`.
- **Check Logs**: `docker-compose logs db` for startup errors.

### Out of memory (OOM)

- Increase Docker memory limit in Docker Desktop settings (if local).
- Optimize Gunicorn workers (reduce count).
- Use `docker stats` to monitor usage.

### Permission errors

- Check file ownership of mounted volumes.
- Fix backend ownership: `chown -R 1000:1000 ./storage` (matches `appuser` UID).

## Security Checklist

- [ ] Strong passwords in `.env`
- [ ] `.env` and secrets NOT committed to git
- [ ] Firewall configured to block direct database port access from internet
- [ ] HTTPS configured (use reverse proxy like Caddy or Nginx with Certbot)
- [ ] Regular backups scheduled (cron job for `backup.sh`)
- [ ] Containers running as non-root users
- [ ] Docker images regular security scanning
