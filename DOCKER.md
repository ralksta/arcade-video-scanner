# Docker Deployment Guide

Run Arcade Media Scanner in a Docker container for easy deployment and portability.

## Quick Start

### Using Docker Compose (Recommended)

1. **Edit `docker-compose.yml`** and update the media path:
   ```yaml
   volumes:
     - /path/to/your/media:/media:ro  # Change this to your actual media directory
   ```

2. **Start the container**:
   ```bash
   docker-compose up -d
   ```

3. **Access the web UI**:
   ```
   http://localhost:8000
   ```

4. **Default credentials**:
   - Username: `admin`
   - Password: `admin`
   - ⚠️ **Change this immediately** in Settings → Users

### Using Docker CLI

```bash
docker run -d \
  --name arcade-scanner \
  -p 8000:8000 \
  -v /path/to/media:/media:ro \
  -v arcade-config:/config \
  -v arcade-cache:/cache \
  -e SKIP_SETUP=true \
  --restart unless-stopped \
  arcade-scanner:latest
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Web UI port |
| `SKIP_SETUP` | `true` | Skip first-run wizard in Docker |
| `CONFIG_DIR` | `/config` | Configuration & database directory |
| `CACHE_DIR` | `/cache` | Thumbnails & cache directory |
| `PUID` | `1000` | User ID for file permissions |
| `PGID` | `1000` | Group ID for file permissions |

### Volume Mounts

| Path | Purpose | Required | Notes |
|------|---------|----------|-------|
| `/media` | Media library | ✅ Yes | Mount your video/image folders here (read-only recommended) |
| `/config` | Persistent data | ✅ Yes | Databases, settings, user data |
| `/cache` | Thumbnails/previews | ⚠️ Recommended | Can be regenerated but slow |

**Example with multiple media directories:**
```yaml
volumes:
  - /mnt/videos:/media/videos:ro
  - /mnt/photos:/media/photos:ro
  - /nas/archive:/media/archive:ro
  - arcade-config:/config
  - arcade-cache:/cache
```

## GPU Support (NVIDIA Only)

### Prerequisites
- NVIDIA GPU with drivers installed on host
- NVIDIA Container Toolkit installed
- Docker version 19.03+

### Enable GPU in Docker Compose
```yaml
services:
  arcade-scanner:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu, video]
```

### Enable GPU with Docker CLI
```bash
docker run -d \
  --name arcade-scanner \
  --gpus all \
  -p 8000:8000 \
  -v /path/to/media:/media:ro \
  -v arcade-config:/config \
  -v arcade-cache:/cache \
  arcade-scanner:latest
```

**Verify GPU access**:
```bash
docker exec arcade-scanner nvidia-smi
```

## Building from Source

```bash
# Clone the repository
git clone https://github.com/your-username/arcade-video-scanner.git
cd arcade-video-scanner

# Build the image
docker build -t arcade-scanner:latest .

# Run
docker-compose up -d
```

## Updating

### Docker Compose
```bash
# Pull latest changes
git pull

# Rebuild image
docker-compose build

# Restart container
docker-compose up -d
```

### Docker CLI
```bash
# Stop and remove old container
docker stop arcade-scanner
docker rm arcade-scanner

# Pull/rebuild latest image
docker build -t arcade-scanner:latest .

# Start new container
docker run -d \
  --name arcade-scanner \
  -p 8000:8000 \
  -v /path/to/media:/media:ro \
  -v arcade-config:/config \
  -v arcade-cache:/cache \
  arcade-scanner:latest
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs arcade-scanner

# Check health status
docker ps --filter "name=arcade-scanner"
```

### Permission errors
If you see permission denied errors:
```bash
# Find your user/group IDs
id

# Update docker-compose.yml with your actual IDs
environment:
  - PUID=1000  # Replace with your UID
  - PGID=1000  # Replace with your GID
```

### Database locked errors
Ensure only one instance is running:
```bash
# Stop all instances
docker stop arcade-scanner

# Start fresh
docker-compose up -d
```

### FFmpeg not found
The Docker image includes FFmpeg. If you see errors:
```bash
# Verify FFmpeg is available
docker exec arcade-scanner ffmpeg -version
docker exec arcade-scanner ffprobe -version
```

### Thumbnails not generating
```bash
# Check cache directory permissions
docker exec arcade-scanner ls -la /cache

# Force rebuild thumbnails (will restart container)
docker-compose down
docker volume rm arcade-cache
docker-compose up -d
```

## Data Backup

### Backup configuration and database
```bash
# Using Docker volumes
docker run --rm \
  -v arcade-config:/source \
  -v $(pwd):/backup \
  alpine tar czf /backup/arcade-config-backup.tar.gz -C /source .
```

### Restore from backup
```bash
docker run --rm \
  -v arcade-config:/target \
  -v $(pwd):/backup \
  alpine tar xzf /backup/arcade-config-backup.tar.gz -C /target
```

## Advanced Configuration

### Custom Port
```yaml
ports:
  - "9000:8000"  # Access on port 9000
```

### Multiple Instances
Run multiple isolated instances:
```bash
# Instance 1
docker run -d \
  --name arcade-scanner-1 \
  -p 8000:8000 \
  -v /media/set1:/media:ro \
  -v arcade-config-1:/config \
  arcade-scanner:latest

# Instance 2
docker run -d \
  --name arcade-scanner-2 \
  -p 8001:8000 \
  -v /media/set2:/media:ro \
  -v arcade-config-2:/config \
  arcade-scanner:latest
```

### Read-only Root Filesystem
For enhanced security:
```yaml
services:
  arcade-scanner:
    read_only: true
    tmpfs:
      - /tmp
```

## Health Monitoring

The container exposes a health check endpoint. Integrate with monitoring:

```bash
# Manual health check
curl http://localhost:8000/

# Docker health status
docker inspect --format='{{.State.Health.Status}}' arcade-scanner
```

## Resource Limits

Prevent the scanner from consuming too many resources:

```yaml
services:
  arcade-scanner:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 4G
        reservations:
          memory: 2G
```

## Network Configuration

### Reverse Proxy (Nginx)
```nginx
location /scanner/ {
    proxy_pass http://localhost:8000/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### Reverse Proxy (Traefik)
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.scanner.rule=Host(`scanner.example.com`)"
  - "traefik.http.services.scanner.loadbalancer.server.port=8000"
```

## Security Best Practices

1. **Change Default Password** immediately after first login
2. **Use Read-Only Mounts** for media directories (`:ro` flag)
3. **Regular Backups** of `/config` volume
4. **Network Isolation** - run in a dedicated Docker network
5. **Keep Updated** - rebuild image regularly for security patches

## Support

- **Issues**: https://github.com/your-username/arcade-video-scanner/issues
- **Documentation**: https://github.com/your-username/arcade-video-scanner/wiki
- **Container Image**: Docker Hub / GHCR (coming soon)
