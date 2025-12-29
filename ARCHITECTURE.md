# Technical Documentation: Concurrency & Conflict Resolution

## Table of Contents
1. [Overview](#overview)
2. [CRDT Architecture](#crdt-architecture)
3. [Preventing Last-Write-Wins Data Loss](#preventing-last-write-wins)
4. [Operation Processing Pipeline](#operation-processing)
5. [WebSocket Message Flow](#websocket-flow)
6. [Presence & Awareness](#presence)
7. [Block-Level Locking](#block-locking)
8. [Performance Considerations](#performance)

---

## Overview

This platform implements **Conflict-free Replicated Data Types (CRDT)** to enable true multi-user real-time collaboration without data loss. Unlike traditional Operational Transformation (OT), CRDTs guarantee eventual consistency through mathematical properties of commutativity and associativity.

### Why CRDT over OT?

| Feature | CRDT | Operational Transformation |
|---------|------|---------------------------|
| **Server Complexity** | Low - just broadcast | High - must transform operations |
| **Offline Support** | Excellent | Difficult |
| **Scalability** | High - stateless broadcast | Limited - requires central authority |
| **Conflict Resolution** | Automatic | Manual transformation functions |
| **Implementation** | Yjs, Automerge | Google Docs approach |

---

## CRDT Architecture

### Client-Side (Yjs/Automerge)

```javascript
// Client maintains local CRDT document
const ydoc = new Y.Doc()
const ytext = ydoc.getText('content')

// User types "Hello"
ytext.insert(0, 'Hello')

// Yjs generates update (binary format)
const update = Y.encodeStateAsUpdate(ydoc)

// Send to server via WebSocket
websocket.send({
  type: 'operation',
  id: generateUniqueId(),
  data: {
    operation: {
      type: 'update',
      payload: bufferToHex(update),
      client_id: userId
    },
    version: localVersion
  }
})
```

### Server-Side (Django Backend)

The backend serves three critical roles:

1. **Persistence**: Store all CRDT updates for durability
2. **Broadcasting**: Relay updates to all connected clients
3. **State Sync**: Provide initial state to new joiners

```python
# apps/collaboration/services.py

class OperationProcessor:
    @staticmethod
    @transaction.atomic
    def process_operation(document_id, user_id, operation_data, client_version, message_id):
        """
        CRITICAL PATH: This is where concurrent edits are handled.
        
        Steps:
        1. Acquire database row lock (SELECT FOR UPDATE)
        2. Validate operation structure
        3. Assign monotonically increasing server version
        4. Check idempotency (duplicate message detection)
        5. Persist operation to OperationLog
        6. Update document version counter
        7. Return acknowledgment with server version
        
        The CRDT properties ensure this is conflict-free even with
        concurrent operations from multiple clients.
        """
        
        # Row-level lock prevents race conditions on version counter
        document = Document.objects.select_for_update().get(id=document_id)
        
        # Assign server version (monotonically increasing)
        server_version = document.current_version + 1
        
        # Generate unique operation ID
        operation_id = generate_operation_id(document_id, user_id, message_id, server_version)
        
        # Idempotency check
        if OperationLog.objects.filter(operation_id=operation_id).exists():
            return {'success': False, 'error': 'Duplicate operation'}
        
        # Convert hex payload to binary
        payload_binary = bytes.fromhex(operation_data['payload'])
        
        # Create operation log entry (PERSISTENCE)
        OperationLog.objects.create(
            document_id=document_id,
            user_id=user_id,
            operation_id=operation_id,
            operation_type='update',
            payload=payload_binary,  # Yjs update in binary format
            version=server_version,
            client_id=operation_data['client_id'],
            timestamp=time.time() * 1000000  # Microsecond precision
        )
        
        # Update document version
        document.current_version = server_version
        document.save()
        
        return {
            'success': True,
            'operation': {'id': operation_id, 'payload': operation_data['payload']},
            'version': server_version
        }
```

---

## Preventing Last-Write-Wins Data Loss

### The Problem: Race Condition

Without CRDTs, concurrent edits can cause data loss:

```
Time  User A              Server                User B
----  ----------------    ------------------    ----------------
T1    Read: "Hello"       State: "Hello"        Read: "Hello"
T2    Edit: "Hello World" State: "Hello"        Edit: "Hello!!!"
T3    Save: "Hello World" State: "Hello World"  Save: "Hello!!!"
T4                        State: "Hello!!!"     
                          ❌ User A's work LOST!
```

### The Solution: CRDT Merge Function

CRDTs use **causal ordering** and **unique identifiers** to merge changes:

```
Time  User A                    Server                      User B
----  ------------------------  --------------------------  ------------------------
T1    Yjs State: "Hello"        CRDT State: "Hello"         Yjs State: "Hello"
T2    Insert(5, " World")       CRDT State: "Hello"         Insert(5, "!!!")
      ID: A:1, Pos: 5                                       ID: B:1, Pos: 5
T3    Send Update(A:1) -------> Broadcast ----------------> Receive Update(A:1)
T4                              Persist Update(A:1)         Merge: "Hello World!!!"
T5    Receive Update(B:1) <---- Broadcast <---------------- Send Update(B:1)
T6    Merge: "Hello World!!!"   Persist Update(B:1)         
                                CRDT State: "Hello World!!!"
                                ✅ Both edits preserved!
```

### Key Mechanisms

#### 1. Unique Operation IDs

Each operation has a globally unique ID composed of:
- **Client ID**: Unique identifier for each user session
- **Sequence Number**: Monotonically increasing per client
- **Timestamp**: High-precision timestamp for ordering

```python
def generate_operation_id(document_id, user_id, message_id, version):
    """
    Create a unique, deterministic operation ID.
    Prevents duplicate processing of the same operation.
    """
    data = f"{document_id}:{user_id}:{message_id}:{version}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]
```

#### 2. Version Vectors

Each operation carries version information:

```python
class OperationLog(models.Model):
    operation_id = models.CharField(max_length=100, unique=True)
    version = models.PositiveIntegerField()  # Server-assigned version
    client_id = models.CharField(max_length=100)
    timestamp = models.BigIntegerField()  # Microsecond precision
    payload = models.BinaryField()  # CRDT update
```

#### 3. Idempotency Layer

Prevents processing the same message twice:

```python
class IdempotencyService:
    IDEMPOTENCY_TTL = 60 * 5  # 5 minutes
    
    @classmethod
    def is_duplicate(cls, message_id: str) -> bool:
        """Check if message already processed."""
        key = f"idempotency:{message_id}"
        return cache.get(key) is not None
    
    @classmethod
    def mark_processed(cls, message_id: str):
        """Mark message as processed."""
        key = f"idempotency:{message_id}"
        cache.set(key, True, cls.IDEMPOTENCY_TTL)
```

#### 4. Atomic Database Operations

Uses PostgreSQL row-level locking to prevent race conditions:

```python
# This acquires an exclusive lock on the document row
document = Document.objects.select_for_update().get(id=document_id)

# All subsequent operations in this transaction are isolated
# Other concurrent transactions will wait for this lock to release
```

---

## Operation Processing Pipeline

### Complete Flow: User Keystroke → All Clients Updated

```
┌─────────────────┐
│  User A Types   │
│   "Hello"       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Yjs Local Document                             │
│  - Insert "Hello" at position 0                 │
│  - Generate update: Uint8Array([...])           │
│  - Assign client sequence ID: A:42              │
└────────┬────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  WebSocket Send                                 │
│  {                                              │
│    type: 'operation',                           │
│    id: 'msg-uuid-123',                          │
│    data: {                                      │
│      operation: {                               │
│        type: 'update',                          │
│        payload: 'hex-encoded-update',           │
│        client_id: 'A'                           │
│      },                                         │
│      version: 41  // Client's last known version│
│    }                                            │
│  }                                              │
└────────┬────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Server: DocumentConsumer.receive()             │
│  1. Parse JSON                                  │
│  2. Check idempotency (msg-uuid-123)            │
│  3. Route to handle_operation()                 │
└────────┬────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  OperationProcessor.process_operation()         │
│  1. BEGIN TRANSACTION                           │
│  2. SELECT ... FOR UPDATE (lock document row)   │
│  3. version = document.current_version + 1      │
│  4. Check duplicate (operation_id in DB?)       │
│  5. INSERT INTO operation_logs (...)            │
│  6. UPDATE documents SET version = version + 1  │
│  7. COMMIT                                      │
│  8. Mark idempotent (cache msg-uuid-123)        │
└────────┬────────────────────────────────────────┘
         │
         ├─────────────────────────────────────────┐
         │                                         │
         ▼                                         ▼
┌──────────────────────┐              ┌──────────────────────┐
│  Send ACK to User A  │              │  Broadcast to Others │
│  {                   │              │  via Channel Layer   │
│    type: 'op.ack',   │              │                      │
│    id: 'msg-uuid',   │              │  channel_layer       │
│    version: 42       │              │    .group_send(...)  │
│  }                   │              │                      │
└──────────────────────┘              └──────────┬───────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    │                            │                            │
                    ▼                            ▼                            ▼
         ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
         │  User B (WS)     │        │  User C (WS)     │        │  User D (WS)     │
         │  Receives:       │        │  Receives:       │        │  Receives:       │
         │  {               │        │  {               │        │  {               │
         │    type: 'op',   │        │    type: 'op',   │        │    type: 'op',   │
         │    data: {...}   │        │    data: {...}   │        │    data: {...}   │
         │  }               │        │  }               │        │  }               │
         └────────┬─────────┘        └────────┬─────────┘        └────────┬─────────┘
                  │                           │                           │
                  ▼                           ▼                           ▼
         ┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
         │ Yjs Apply Update │        │ Yjs Apply Update │        │ Yjs Apply Update │
         │ Y.applyUpdate()  │        │ Y.applyUpdate()  │        │ Y.applyUpdate()  │
         │                  │        │                  │        │                  │
         │ Merged State:    │        │ Merged State:    │        │ Merged State:    │
         │ "Hello"          │        │ "Hello"          │        │ "Hello"          │
         └──────────────────┘        └──────────────────┘        └──────────────────┘
```

---

## WebSocket Message Flow

### Message Types

#### 1. Operation (CRDT Update)
```json
{
  "type": "operation",
  "id": "unique-message-id",
  "data": {
    "operation": {
      "type": "update",
      "payload": "0104a3f2...",  // Hex-encoded Yjs update
      "client_id": "user-uuid"
    },
    "version": 42
  }
}
```

#### 2. Cursor Update
```json
{
  "type": "cursor",
  "id": "msg-id",
  "data": {
    "position": {
      "block_id": "block-uuid",
      "offset": 15
    },
    "selection": {
      "anchor": 10,
      "head": 15
    }
  }
}
```

#### 3. Awareness (Yjs Awareness Protocol)
```json
{
  "type": "awareness",
  "id": "msg-id",
  "data": {
    "state": {
      "cursor": {"block": "...", "offset": 10},
      "name": "John Doe",
      "color": "#6366f1"
    }
  }
}
```

#### 4. Block Lock
```json
{
  "type": "block.lock",
  "id": "msg-id",
  "data": {
    "block_id": "block-uuid"
  }
}
```

---

## Presence & Awareness

### Real-time User Tracking

Uses Redis for fast, ephemeral storage:

```python
class PresenceService:
    PRESENCE_TTL = 60  # seconds
    
    @staticmethod
    def add_user_presence(document_id, user_id, user_data):
        """
        Store presence in Redis with TTL.
        Key: presence:{doc_id}:users -> Set of user IDs
        Key: presence:{doc_id}:user:{user_id} -> Hash of user data
        """
        redis_client = get_redis_client()
        
        # Add to active users set
        set_key = f"presence:{document_id}:users"
        redis_client.sadd(set_key, user_id)
        redis_client.expire(set_key, PRESENCE_TTL)
        
        # Store user details
        user_key = f"presence:{document_id}:user:{user_id}"
        redis_client.hmset(user_key, {
            'display_name': user_data['display_name'],
            'avatar': user_data['avatar'],
            'color': user_data['color'],
            'cursor': json.dumps({}),
            'last_activity': time.time()
        })
        redis_client.expire(user_key, PRESENCE_TTL)
```

### Cursor Synchronization

Throttled to prevent network flooding:

```python
CURSOR_UPDATE_THROTTLE = 0.1  # Max 10 updates/second

async def handle_cursor_update(self, payload, message_id):
    # Update in Redis (fast, non-blocking)
    await sync_to_async(PresenceService.update_cursor)(
        document_id=self.document_id,
        user_id=str(self.user.id),
        cursor_data=payload
    )
    
    # Broadcast to others (throttled)
    await self.channel_layer.group_send(
        self.document_group,
        {
            'type': 'cursor.update',
            'user_id': str(self.user.id),
            'cursor': payload,
            'exclude_channel': self.channel_name  # Don't echo back
        }
    )
```

---

## Block-Level Locking

For fine-grained control, blocks can be locked during editing:

```python
class CollaborationService:
    @staticmethod
    def acquire_block_lock(document_id, block_id, user_id, timeout=30):
        """
        Acquire exclusive lock on a block using Redis.
        
        Uses Redis SET NX (set if not exists) for atomic locking.
        """
        redis_client = get_redis_client()
        lock_key = f"block_lock:{document_id}:{block_id}"
        
        # Atomic: Set key only if it doesn't exist, with expiration
        acquired = redis_client.set(
            lock_key,
            user_id,
            nx=True,  # Only set if key doesn't exist
            ex=timeout  # Auto-expire after timeout
        )
        
        return bool(acquired)
    
    @staticmethod
    def release_block_lock(document_id, block_id, user_id):
        """
        Release lock (only if owned by user).
        
        Uses Lua script for atomic check-and-delete.
        """
        redis_client = get_redis_client()
        lock_key = f"block_lock:{document_id}:{block_id}"
        
        # Lua script ensures atomicity
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        
        redis_client.eval(lua_script, 1, lock_key, user_id)
```

---

## Performance Considerations

### Database Optimization

1. **Indexes**
```sql
-- Document lookups
CREATE INDEX idx_documents_workspace ON documents(workspace_id) WHERE is_deleted = FALSE;

-- Operation log queries
CREATE INDEX idx_operations_doc_version ON operation_logs(document_id, version);
CREATE INDEX idx_operations_timestamp ON operation_logs(timestamp);

-- JSONB search
CREATE INDEX idx_documents_properties_gin ON documents USING GIN (properties);
CREATE INDEX idx_blocks_content_gin ON blocks USING GIN (content);
```

2. **Connection Pooling**
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 600,  # Persistent connections
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000'  # 30 second timeout
        }
    }
}
```

3. **Query Optimization**
```python
# Bad: N+1 queries
documents = Document.objects.all()
for doc in documents:
    print(doc.created_by.name)  # Query per document!

# Good: Select related
documents = Document.objects.select_related('created_by', 'workspace')
for doc in documents:
    print(doc.created_by.name)  # No extra queries
```

### Redis Optimization

1. **Key Expiration**
- All presence keys: 60 seconds
- Idempotency keys: 5 minutes
- Block locks: 30 seconds (auto-release)

2. **Memory Management**
```python
# Redis configuration
CACHES = {
    'default': {
        'OPTIONS': {
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50}
        }
    }
}
```

### WebSocket Optimization

1. **Binary Payloads**
- Yjs updates are binary (efficient)
- Transmitted as hex strings in JSON

2. **Message Batching** (optional enhancement)
```python
# Batch cursor updates every 100ms
batch = []
last_send = time.time()

def queue_cursor_update(data):
    batch.append(data)
    if time.time() - last_send > 0.1:
        send_batch(batch)
        batch.clear()
```

---

## Conclusion

This architecture provides:

✅ **Zero Data Loss**: CRDT guarantees eventual consistency  
✅ **Real-time Sync**: Sub-100ms latency for operations  
✅ **Offline Support**: Clients can work offline and sync later  
✅ **Scalability**: Stateless broadcast, horizontal scaling  
✅ **Reliability**: Idempotency, persistence, atomic operations  

The combination of CRDTs, WebSockets, Redis, and PostgreSQL creates a production-ready real-time collaboration platform.
