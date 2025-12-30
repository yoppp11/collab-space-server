"""
Tests for Collaboration Services
"""
import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from apps.collaboration.services import (
    CRDTService,
    OperationProcessor,
    PresenceService,
    CollaborationService,
)
from apps.core.tests.factories import UserFactory, DocumentFactory
from apps.collaboration.models import OperationLog, CollaborationSession


@pytest.mark.django_db
class TestCRDTService:
    """Test CRDT service methods"""
    
    def test_get_document_state_success(self):
        """Test getting document state successfully"""
        document = DocumentFactory(current_version=5)
        
        # Create some operation logs
        for i in range(3):
            OperationLog.objects.create(
                document_id=document.id,
                user_id=document.created_by_id,
                operation_id=f"op_{i}",
                operation_type='update',
                payload=b'\x00\x01\x02',
                version=i + 1,
                client_id='client_1',
                timestamp=1000000 + i
            )
        
        result = CRDTService.get_document_state(str(document.id))
        
        assert result['document_id'] == str(document.id)
        assert result['version'] == 5
        assert 'updates' in result
        assert len(result['updates']) == 3
    
    def test_get_document_state_not_found(self):
        """Test getting state for non-existent document"""
        result = CRDTService.get_document_state('00000000-0000-0000-0000-000000000000')
        
        assert 'error' in result
        assert result['error'] == 'Document not found'
    
    def test_apply_state_vector(self):
        """Test applying state vector to get missing operations"""
        document = DocumentFactory()
        
        # Create operations with different versions
        for i in range(5):
            OperationLog.objects.create(
                document_id=document.id,
                user_id=document.created_by_id,
                operation_id=f"op_{i}",
                operation_type='update',
                payload=f'payload_{i}'.encode(),
                version=i + 1,
                client_id='client_1',
                timestamp=1000000 + i
            )
        
        # Client has version 2, should get versions 3, 4, 5
        client_state_vector = {'version': 2}
        missing_ops = CRDTService.apply_state_vector(str(document.id), client_state_vector)
        
        assert len(missing_ops) == 3
        assert missing_ops[0] == b'payload_2'


@pytest.mark.django_db
class TestOperationProcessor:
    """Test operation processing"""
    
    def test_process_operation_success(self):
        """Test successful operation processing"""
        document = DocumentFactory(current_version=1)
        user = UserFactory()
        
        operation_data = {
            'type': 'update',
            'payload': 'deadbeef',  # hex string
            'client_id': 'client_1',
        }
        
        result = OperationProcessor.process_operation(
            document_id=str(document.id),
            user_id=str(user.id),
            operation_data=operation_data,
            client_version=1,
            message_id='msg_1'
        )
        
        assert result['success'] is True
        assert 'operation' in result
        assert result['version'] == 2
        
        # Verify document updated
        document.refresh_from_db()
        assert document.current_version == 2
        assert document.last_edited_by_id == user.id
    
    def test_process_operation_invalid_format(self):
        """Test operation with invalid format"""
        document = DocumentFactory()
        user = UserFactory()
        
        operation_data = {
            'type': 'update',
            # Missing payload
        }
        
        result = OperationProcessor.process_operation(
            document_id=str(document.id),
            user_id=str(user.id),
            operation_data=operation_data,
            client_version=1,
            message_id='msg_1'
        )
        
        assert result['success'] is False
        assert 'error' in result
    
    def test_process_operation_duplicate(self):
        """Test duplicate operation detection"""
        document = DocumentFactory()
        user = UserFactory()
        
        # Create an operation directly in the database
        from apps.collaboration.models import OperationLog
        existing_op_id = OperationProcessor._generate_operation_id(
            str(document.id), str(user.id), 'msg_1', 2  # version 2 since doc starts at 1
        )
        OperationLog.objects.create(
            document_id=document.id,
            user_id=user.id,
            operation_id=existing_op_id,
            operation_type='update',
            payload=b'\xde\xad\xbe\xef',
            version=2,
            client_id='client_1',
            timestamp=1000000
        )
        
        # Try to process operation that would generate the same operation_id
        operation_data = {
            'type': 'update',
            'payload': 'deadbeef',
            'client_id': 'client_1',
        }
        
        result = OperationProcessor.process_operation(
            document_id=str(document.id),
            user_id=str(user.id),
            operation_data=operation_data,
            client_version=1,
            message_id='msg_1'  # Same message_id, and version will be 2
        )
        
        assert result['success'] is False
        assert 'Duplicate operation' in result['error']
    
    def test_process_operation_document_not_found(self):
        """Test operation on non-existent document"""
        user = UserFactory()
        
        operation_data = {
            'type': 'update',
            'payload': 'deadbeef',
        }
        
        result = OperationProcessor.process_operation(
            document_id='00000000-0000-0000-0000-000000000000',
            user_id=str(user.id),
            operation_data=operation_data,
            client_version=1,
            message_id='msg_1'
        )
        
        assert result['success'] is False
        assert 'not found' in result['error']
    
    def test_validate_operation(self):
        """Test operation validation"""
        valid_op = {
            'type': 'update',
            'payload': 'deadbeef',
        }
        assert OperationProcessor._validate_operation(valid_op) is True
        
        invalid_op = {
            'type': 'update',
            # Missing payload
        }
        assert OperationProcessor._validate_operation(invalid_op) is False
    
    def test_generate_operation_id(self):
        """Test operation ID generation"""
        op_id = OperationProcessor._generate_operation_id(
            document_id='doc_1',
            user_id='user_1',
            message_id='msg_1',
            version=1
        )
        
        assert isinstance(op_id, str)
        assert len(op_id) == 32
        
        # Same inputs should generate same ID
        op_id2 = OperationProcessor._generate_operation_id(
            document_id='doc_1',
            user_id='user_1',
            message_id='msg_1',
            version=1
        )
        assert op_id == op_id2


@pytest.mark.django_db
class TestPresenceService:
    """Test presence service"""
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_get_active_users(self, mock_redis):
        """Test getting active users"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        # Mock Redis responses
        mock_client.smembers.return_value = ['user_1', 'user_2']
        mock_client.hgetall.side_effect = [
            {
                'display_name': 'User 1',
                'avatar': '',
                'color': '#6366f1',
                'cursor': '{}',
                'last_activity': '1234567890.0',
            },
            {
                'display_name': 'User 2',
                'avatar': '',
                'color': '#ef4444',
                'cursor': '{}',
                'last_activity': '1234567891.0',
            }
        ]
        
        users = PresenceService.get_active_users('doc_1')
        
        assert len(users) == 2
        assert users[0]['user_id'] == 'user_1'
        assert users[0]['display_name'] == 'User 1'
        assert users[1]['user_id'] == 'user_2'
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_add_user_presence(self, mock_redis):
        """Test adding user presence"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        PresenceService.add_user_presence(
            document_id='doc_1',
            user_id='user_1',
            user_data={
                'display_name': 'Test User',
                'avatar': 'avatar.jpg',
                'color': '#6366f1',
            }
        )
        
        # Verify Redis calls
        mock_client.sadd.assert_called()
        mock_client.hmset.assert_called()
        assert mock_client.expire.call_count == 2
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_remove_user_presence(self, mock_redis):
        """Test removing user presence"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        PresenceService.remove_user_presence('doc_1', 'user_1')
        
        mock_client.srem.assert_called_once()
        mock_client.delete.assert_called_once()
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_update_cursor(self, mock_redis):
        """Test updating cursor position"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        cursor_data = {'line': 5, 'column': 10}
        PresenceService.update_cursor('doc_1', 'user_1', cursor_data)
        
        # Verify cursor data was serialized and set
        assert mock_client.hset.call_count == 2
        mock_client.expire.assert_called()
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_update_awareness(self, mock_redis):
        """Test updating awareness state"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        state = {'selection': {'start': 0, 'end': 5}}
        PresenceService.update_awareness('doc_1', 'user_1', state)
        
        mock_client.set.assert_called_once()
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_update_activity(self, mock_redis):
        """Test updating activity timestamp"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        PresenceService.update_activity('doc_1', 'user_1')
        
        mock_client.hset.assert_called()
        mock_client.expire.assert_called()


@pytest.mark.django_db
class TestCollaborationService:
    """Test collaboration service"""
    
    @patch('apps.collaboration.services.PresenceService.add_user_presence')
    def test_create_session(self, mock_presence):
        """Test creating collaboration session"""
        document = DocumentFactory()
        user = UserFactory()
        
        result = CollaborationService.create_session(
            document_id=str(document.id),
            user_id=str(user.id),
            channel_name='channel_1'
        )
        
        assert 'session_id' in result
        assert 'color' in result
        
        # Verify session created
        session = CollaborationSession.objects.get(id=result['session_id'])
        assert session.user_id == user.id
        assert session.document_id == document.id
        
        # Verify presence was updated
        mock_presence.assert_called_once()
    
    @patch('apps.collaboration.services.PresenceService.remove_user_presence')
    def test_end_session(self, mock_presence):
        """Test ending collaboration session"""
        document = DocumentFactory()
        user = UserFactory()
        session = CollaborationSession.objects.create(
            document_id=document.id,
            user_id=user.id,
            channel_name='channel_1',
            color='#6366f1'
        )
        
        CollaborationService.end_session(str(document.id), str(user.id))
        
        # Verify session deactivated
        session.refresh_from_db()
        assert session.is_active is False
        
        # Verify presence removed
        mock_presence.assert_called_once()
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_acquire_block_lock_success(self, mock_redis):
        """Test acquiring block lock successfully"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.set.return_value = True
        
        result = CollaborationService.acquire_block_lock(
            document_id='doc_1',
            block_id='block_1',
            user_id='user_1'
        )
        
        assert result is True
        mock_client.set.assert_called_once()
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_acquire_block_lock_already_locked(self, mock_redis):
        """Test acquiring already locked block"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.set.return_value = False
        
        result = CollaborationService.acquire_block_lock(
            document_id='doc_1',
            block_id='block_1',
            user_id='user_1'
        )
        
        assert result is False
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_release_block_lock(self, mock_redis):
        """Test releasing block lock"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        
        CollaborationService.release_block_lock(
            document_id='doc_1',
            block_id='block_1',
            user_id='user_1'
        )
        
        mock_client.eval.assert_called_once()
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_get_block_lock_owner(self, mock_redis):
        """Test getting block lock owner"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = 'user_1'
        
        owner = CollaborationService.get_block_lock_owner('doc_1', 'block_1')
        
        assert owner == 'user_1'
    
    @patch('apps.collaboration.services.get_redis_client')
    def test_get_block_lock_owner_unlocked(self, mock_redis):
        """Test getting owner when block is unlocked"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = None
        
        owner = CollaborationService.get_block_lock_owner('doc_1', 'block_1')
        
        assert owner is None
