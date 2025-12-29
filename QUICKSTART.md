# Quick Start Guide

## Prerequisites

- Docker & Docker Compose installed
- Git installed
- (Optional) Python 3.11+ for local development

## Installation in 5 Minutes

### Step 1: Clone and Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/realtime-collaboration-platform.git
cd realtime-collaboration-platform

# Copy environment file
cp .env.example .env

# (Optional) Edit .env if needed
nano .env
```

### Step 2: Start with Docker

```bash
# Build and start all services
docker-compose up -d --build

# Check status
docker-compose ps

# You should see:
# - collab_postgres (healthy)
# - collab_redis (healthy)
# - collab_web (up)
# - collab_celery_worker (up)
# - collab_celery_beat (up)
```

### Step 3: Initialize Database

```bash
# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Follow prompts:
# Email: admin@example.com
# Password: (your choice)
```

### Step 4: Test the API

```bash
# Get API token
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "yourpassword"}'

# Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbG...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbG...",
  "user": {...}
}

# Test authenticated endpoint
curl http://localhost:8000/api/v1/workspaces/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Step 5: Connect via WebSocket

```javascript
// In browser console or Node.js
const ws = new WebSocket('ws://localhost:8000/ws/notifications/?token=YOUR_ACCESS_TOKEN');

ws.onopen = () => {
  console.log('Connected!');
};

ws.onmessage = (event) => {
  console.log('Notification:', JSON.parse(event.data));
};
```

## Common Operations

### Create a Workspace

```bash
curl -X POST http://localhost:8000/api/v1/workspaces/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Workspace",
    "description": "Testing the platform",
    "icon": "🚀"
  }'
```

### Create a Document

```bash
curl -X POST http://localhost:8000/api/v1/documents/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace": "WORKSPACE_ID",
    "title": "My First Document"
  }'
```

### Connect to Document for Real-time Editing

```javascript
const documentId = 'YOUR_DOCUMENT_ID';
const token = 'YOUR_JWT_TOKEN';

const ws = new WebSocket(`ws://localhost:8000/ws/documents/${documentId}/?token=${token}`);

ws.onopen = () => {
  console.log('Connected to document');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch(message.type) {
    case 'connection.established':
      console.log('Session:', message.data.session_id);
      console.log('Active users:', message.data.active_users);
      break;
    
    case 'operation':
      console.log('Remote edit:', message.data);
      // Apply to local CRDT state
      break;
    
    case 'user.joined':
      console.log('User joined:', message.data);
      break;
  }
};

// Send an operation
ws.send(JSON.stringify({
  type: 'operation',
  id: 'unique-msg-id-' + Date.now(),
  data: {
    operation: {
      type: 'update',
      payload: 'hex-encoded-yjs-update',
      client_id: 'my-client-id'
    },
    version: 0
  }
}));
```

## Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f celery_worker

# Last 100 lines
docker-compose logs --tail=100 web
```

## Stopping the Platform

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes data)
docker-compose down -v
```

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Change port in docker-compose.yml:
# ports:
#   - "8001:8000"  # External:Internal
```

### Database Migration Errors

```bash
# Reset database (⚠️ deletes all data)
docker-compose down -v
docker-compose up -d postgres redis
docker-compose exec web python manage.py migrate
```

### Celery Not Processing Tasks

```bash
# Check worker is running
docker-compose ps celery_worker

# Restart worker
docker-compose restart celery_worker

# Check for errors
docker-compose logs celery_worker
```

## Next Steps

1. **Read the Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md) for concurrency details
2. **Explore the API**: See [API.md](API.md) for complete endpoint reference
3. **Frontend Integration**: Use Yjs library for collaborative editing
4. **Deploy to Production**: See deployment section in README.md

## Development Mode

For local development without Docker:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (via Docker)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15
docker run -d -p 6379:6379 redis:7

# Run migrations
python manage.py migrate

# Start Django (in terminal 1)
python manage.py runserver

# Start Celery worker (in terminal 2)
celery -A config worker -l info

# Start Celery beat (in terminal 3)
celery -A config beat -l info
```

## Admin Interface

Access the Django admin at: http://localhost:8000/admin/

Features:
- View/edit users, workspaces, documents
- Monitor collaboration sessions
- Check operation logs
- Manage notifications

## Need Help?

- Check [README.md](README.md) for detailed documentation
- See [ARCHITECTURE.md](ARCHITECTURE.md) for technical deep dive
- Open an issue on GitHub for bugs/questions
