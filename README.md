# Real-time Collaboration Platform

A robust, scalable backend for a real-time collaboration platform built with Django, Django Channels, and CRDT synchronization.

## Features

### 🎯 Core Functionality
- **Real-time Collaborative Editing**: Multi-user concurrent editing with CRDT (Conflict-free Replicated Data Types) support
- **Block-based Documents**: Notion-style hierarchical content blocks using MPTT (Modified Preorder Tree Traversal)
- **Workspace Management**: Multi-tenant workspaces with granular RBAC (Role-Based Access Control)
- **Kanban Boards**: Trello-style boards, lists, and cards
- **Real-time Presence**: Live user cursors, typing indicators, and awareness states
- **Version Control**: Complete document version history and restore functionality
- **Comments & Mentions**: Threaded comments with user mentions and notifications

### 🔒 Security & Permissions
- **Granular RBAC**: Workspace, Board, and Document-level permissions
- **JWT Authentication**: Secure token-based authentication with rotation
- **WebSocket Security**: JWT authentication for WebSocket connections
- **Role Hierarchy**: Owner → Admin → Member → Guest

### ⚡ Performance & Scalability
- **Redis Caching**: Hot data caching for active sessions and presence
- **PostgreSQL Indexing**: GIN indexes for JSONB fields, optimized queries
- **Celery Background Tasks**: Async processing for notifications, exports, cleanup
- **Idempotency**: Duplicate message detection for WebSocket operations
- **Connection Pooling**: Optimized database and Redis connections

## Architecture

```
├── config/                 # Django configuration
│   ├── settings/          # Environment-specific settings
│   ├── asgi.py            # ASGI configuration for WebSockets
│   ├── celery.py          # Celery configuration
│   └── urls.py            # URL routing
├── apps/
│   ├── core/              # Base models, utilities, exceptions
│   ├── users/             # User authentication and management
│   ├── workspaces/        # Workspaces, boards, RBAC
│   ├── documents/         # Documents and blocks (MPTT)
│   ├── collaboration/     # WebSocket consumers, CRDT, presence
│   └── notifications/     # Real-time notifications
├── docker-compose.yml     # Docker orchestration
├── Dockerfile             # Application container
└── requirements.txt       # Python dependencies
```

## Technology Stack

- **Framework**: Django 5.0+ with Django REST Framework
- **Async Engine**: Django Channels (ASGI) with Redis Channel Layer
- **Database**: PostgreSQL 15+ (JSONB, GIN indexes)
- **Cache/Queue**: Redis 7+
- **Task Queue**: Celery with Redis broker
- **Web Server**: Uvicorn (ASGI), Gunicorn (fallback)
- **Containerization**: Docker & Docker Compose

## Installation & Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+
- Redis 7+

### Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/realtime-collaboration-platform.git
   cd realtime-collaboration-platform
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Build and start containers**
   ```bash
   docker-compose up -d --build
   ```

4. **Run migrations**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

6. **Access the application**
   - API: http://localhost:8000/api/v1/
   - Admin: http://localhost:8000/admin/
   - WebSocket: ws://localhost:8000/ws/

### Local Development Setup

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL and Redis**
   ```bash
   # Start PostgreSQL and Redis (via Docker or system services)
   docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:15
   docker run -d -p 6379:6379 redis:7
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Start development servers**
   ```bash
   # Terminal 1: Django/Channels server
   python manage.py runserver
   
   # Terminal 2: Celery worker
   celery -A config worker -l info
   
   # Terminal 3: Celery beat
   celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
   ```

## API Documentation

### Authentication
- `POST /api/v1/auth/register/` - User registration
- `POST /api/v1/auth/login/` - JWT token authentication
- `POST /api/v1/auth/token/refresh/` - Refresh access token
- `POST /api/v1/auth/logout/` - Logout (blacklist token)

### Workspaces
- `GET /api/v1/workspaces/` - List user workspaces
- `POST /api/v1/workspaces/` - Create workspace
- `GET /api/v1/workspaces/{id}/` - Get workspace details
- `POST /api/v1/workspaces/{id}/invite/` - Invite member
- `GET /api/v1/workspaces/{id}/boards/` - List boards

### Documents
- `GET /api/v1/documents/` - List documents
- `POST /api/v1/documents/` - Create document
- `GET /api/v1/documents/{id}/` - Get document with blocks
- `POST /api/v1/documents/{id}/duplicate/` - Duplicate document
- `GET /api/v1/documents/{id}/versions/` - Version history

### WebSocket Connections

#### Document Collaboration
```javascript
// Connect to document
const ws = new WebSocket('ws://localhost:8000/ws/documents/{documentId}/?token={jwt}');

// Send operation
ws.send(JSON.stringify({
  type: 'operation',
  id: 'unique-message-id',
  data: {
    operation: {
      type: 'update',
      payload: '...', // Yjs/Automerge binary update (hex)
      client_id: 'user-123'
    },
    version: 42
  }
}));

// Receive operation broadcast
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'operation') {
    // Apply operation to local CRDT state
  }
};
```

## Concurrency & Conflict Resolution

### How Data Loss is Prevented

This platform uses **CRDT (Conflict-free Replicated Data Types)** to ensure zero data loss during concurrent editing:

1. **Commutative Operations**: All operations can be applied in any order
2. **Version Vectors**: Each operation has a unique version number
3. **Causal Ordering**: Operations preserve happened-before relationships
4. **Idempotency**: Duplicate messages are detected and ignored via message IDs
5. **Persistence**: All operations are logged before acknowledgment

### CRDT Integration

The backend is designed to work with **Yjs** (recommended) or **Automerge** on the client side:

**With Yjs:**
```javascript
import * as Y from 'yjs'
import { WebsocketProvider } from 'y-websocket'

const ydoc = new Y.Doc()
const provider = new WebsocketProvider(
  'ws://localhost:8000/ws/documents/123/?token=...',
  'document-123',
  ydoc
)
```

**Backend Role:**
1. Receives binary CRDT updates from clients
2. Persists updates in `OperationLog` table
3. Broadcasts updates to all connected clients
4. Provides initial state for new joiners
5. Handles compression and snapshots

### Operation Processing Flow

```
Client A                Server                   Client B
   |                       |                         |
   |--- operation(v42) --->|                         |
   |                       |--- validate ----------->|
   |                       |--- persist ------------->|
   |                       |                         |
   |<--- ack(v43) ---------|                         |
   |                       |--- broadcast(v43) ----->|
   |                       |                         |
```

## Database Schema Highlights

### Key Models

**Document**: Top-level content container
- Stores CRDT state for sync
- Tracks version number
- Links to workspace and board

**Block**: Hierarchical content blocks (MPTT)
- Supports 15+ block types (text, heading, todo, code, etc.)
- Nested structure for pages-within-pages
- Stores content as JSONB

**OperationLog**: CRDT operation history
- Binary payload storage
- Version sequencing
- Timestamp for ordering

**WorkspaceMembership**: RBAC implementation
- Role: Owner, Admin, Member, Guest
- Permission caching

## Performance Optimizations

1. **Database Indexes**:
   - GIN indexes on JSONB fields
   - Composite indexes on foreign keys + filters
   - Covering indexes for common queries

2. **Caching Strategy**:
   - User permissions (5 min TTL)
   - Active presence (60 sec TTL)
   - Document state snapshots

3. **Query Optimization**:
   - `select_related()` for foreign keys
   - `prefetch_related()` for reverse relations
   - `only()` / `defer()` for large fields

4. **WebSocket Efficiency**:
   - Binary payloads (Yjs updates)
   - Message batching
   - Throttled cursor updates

## Celery Tasks

### Scheduled Tasks (Celery Beat)
- `cleanup_expired_sessions` - Every 5 minutes
- `cleanup_old_versions` - Daily at 3 AM
- `send_pending_notifications` - Every minute
- `generate_activity_reports` - Weekly

### On-Demand Tasks
- `send_workspace_invitation_email`
- `export_document_pdf`
- `compress_operation_logs`
- `index_document_for_search`

## Production Deployment

### Environment Configuration

See `.env.example` for required variables.

### Security Checklist

- [ ] Set `DEBUG=False`
- [ ] Use strong `DJANGO_SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Enable SSL/HTTPS
- [ ] Set up CORS properly
- [ ] Use environment variables for secrets
- [ ] Enable Sentry for error tracking
- [ ] Configure rate limiting
- [ ] Set up database backups
- [ ] Use Redis persistence (AOF)

### Scaling

**Horizontal Scaling:**
- Multiple Uvicorn workers behind load balancer
- Dedicated Celery workers for different queues
- Redis Cluster for channel layer
- PostgreSQL read replicas

**Vertical Scaling:**
- Increase Uvicorn workers based on CPU cores
- Tune PostgreSQL `shared_buffers`, `work_mem`
- Increase Redis `maxmemory`

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=apps --cov-report=html

# Specific app
pytest apps/collaboration/tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Acknowledgments

- **Yjs**: CRDT library for real-time collaboration
- **Django Channels**: WebSocket support for Django
- **Django MPTT**: Efficient tree structures
- **Celery**: Distributed task queue

## Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/yourusername/realtime-collaboration-platform/issues)
- Documentation: [Wiki](https://github.com/yourusername/realtime-collaboration-platform/wiki)

---

**Built with ❤️ by Senior Software Architects**
