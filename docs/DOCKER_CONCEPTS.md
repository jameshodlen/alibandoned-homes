# Docker Concepts Explained

## What is Docker?

**Container:** Lightweight, isolated environment

- Like a virtual machine but shares the host OS kernel.
- **Faster**: Starts in seconds.
- **Efficient**: Uses less memory/CPU.
- **Portable**: Runs anywhere Docker is installed.

**Image:** Read-only blueprint for a container

- Built from a `Dockerfile`.
- Layers: Changes are stacked (e.g., OS -> Python -> Dependencies -> App Code).
- Stored in a Registry (e.g., Docker Hub).

**Volume:** Persistent storage

- Data in containers is ephemeral (lost when container deleted).
- Volumes exist outside the container filesystem.
- Survives restart/removal.

## Docker Compose

Tool for defining and running multi-container applications.

- **Orchestration**: Manage Backend, Frontend, DB, Redis together.
- **Networking**: Automatically creates a private network where services find each other by name (e.g., `db`).
- **Configuration**: Defined in `docker-compose.yml`.

## Why Use Docker?

1. **Consistency (Infrastructure as Code)**

   - "Works on my machine" means it works on production.
   - Env definitions live in code (`Dockerfile`).

2. **Isolation**

   - Dependencies don't conflict (e.g., App A needs Python 3.8, App B needs 3.11).
   - Security: If one app is compromised, others are isolated.

3. **Scalability**
   - Easy to spin up multiple replicas of a service.
   - cloud-native friendly.

## Common Architecture Patterns

### Multi-Stage Builds

Builds occur in stages to optimize image size.

1. **Builder Stage**: Has compilers (gcc), headers, full SDK. Builds the artifact.
2. **Runtime Stage**: Has minimal runtime (slim OS). Copies artifact from Builder.
   Result: Tiny, secure production image without build tools.

### Sidecar Pattern (Logging/Monitoring)

Running a helper container alongside your main app (e.g., Nginx sidecar for SSL, or Logstash for shipping logs).

## Common Commands Guide

```bash
# Build images defined in compose file
docker-compose build

# Start services in background (-d)
docker-compose up -d

# Stop services and remove containers
docker-compose down

# View logs (follow with -f)
docker-compose logs -f

# Execute command inside running container
docker-compose exec <service_name> <command>
# Example: docker-compose exec backend python manage.py migrate

# Rebuild and restart specific service
docker-compose up -d --build backend
```
