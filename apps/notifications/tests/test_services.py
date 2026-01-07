"""
Unit tests for Notification services.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.core.tests.factories import (
    UserFactory, WorkspaceFactory, WorkspaceMembershipFactory,
    BoardFactory, DocumentFactory, CommentFactory
)

pytestmark = pytest.mark.django_db


class TestNotificationService:
    """Tests for NotificationService."""
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_create_notification(self, mock_channel_layer, user):
        """Test creating a notification."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        notification = NotificationService.create_notification(
            recipient=user,
            notification_type=Notification.NotificationType.MENTION,
            title='Test Title',
            message='Test message',
            actor=None,
            action_url='/test/url',
            content_type='test',
            object_id=None,
            metadata={'key': 'value'}
        )
        
        assert notification.recipient == user
        assert notification.title == 'Test Title'
        assert notification.message == 'Test message'
        assert notification.notification_type == 'mention'
        assert notification.action_url == '/test/url'
        assert notification.metadata == {'key': 'value'}
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_create_notification_with_actor(self, mock_channel_layer, user):
        """Test creating a notification with an actor."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        actor = UserFactory()
        notification = NotificationService.create_notification(
            recipient=user,
            notification_type=Notification.NotificationType.COMMENT,
            title='Comment notification',
            message='Someone commented',
            actor=actor
        )
        
        assert notification.actor == actor
        assert notification.recipient == user
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_send_realtime_notification(self, mock_channel_layer, user):
        """Test sending a real-time notification via WebSocket."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        notification = Notification.objects.create(
            recipient=user,
            notification_type='mention',
            title='Test',
            message='Test message'
        )
        
        NotificationService.send_realtime_notification(notification)
        
        mock_layer.group_send.assert_called_once()
        call_args = mock_layer.group_send.call_args
        assert f'user_{user.id}' in call_args[0]
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_notify_mention(self, mock_channel_layer, user):
        """Test notifying user of a mention."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        mentioner = UserFactory()
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        comment = CommentFactory(document=document, author=mentioner)
        
        notification = NotificationService.notify_mention(
            mentioned_user=user,
            mentioner=mentioner,
            document=document,
            comment=comment
        )
        
        assert notification.recipient == user
        assert notification.notification_type == 'mention'
        assert notification.actor == mentioner
        assert f'{mentioner.display_name} mentioned you' in notification.title
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_notify_comment(self, mock_channel_layer, user):
        """Test notifying user of a comment."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        commenter = UserFactory()
        workspace = WorkspaceFactory(owner=user)
        document = DocumentFactory(workspace=workspace, created_by=user)
        comment = CommentFactory(document=document, author=commenter)
        
        notification = NotificationService.notify_comment(
            recipient=user,
            commenter=commenter,
            document=document,
            comment=comment
        )
        
        assert notification.recipient == user
        assert notification.notification_type == 'comment'
        assert notification.actor == commenter
        assert f'{commenter.display_name} commented' in notification.title
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_notify_workspace_member_joined(self, mock_channel_layer, user):
        """Test notifying workspace members when a new member joins."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        workspace = WorkspaceFactory(owner=user)
        existing_member = UserFactory()
        new_member = UserFactory()
        
        # Create memberships
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        WorkspaceMembershipFactory(workspace=workspace, user=existing_member, role='member')
        
        NotificationService.notify_workspace_member_joined(
            workspace=workspace,
            new_member=new_member,
            invited_by=user
        )
        
        # Should create notifications for owner and existing member
        notifications = Notification.objects.filter(
            notification_type='workspace'
        )
        assert notifications.count() == 2
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_notify_workspace_member_joined_without_inviter(self, mock_channel_layer, user):
        """Test notifying workspace members when a new member joins without inviter."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        workspace = WorkspaceFactory(owner=user)
        new_member = UserFactory()
        
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        
        NotificationService.notify_workspace_member_joined(
            workspace=workspace,
            new_member=new_member,
            invited_by=None
        )
        
        notification = Notification.objects.filter(
            recipient=user,
            notification_type='workspace'
        ).first()
        
        assert notification is not None
        assert notification.metadata['invited_by_id'] is None
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_notify_board_created(self, mock_channel_layer, user):
        """Test notifying workspace members when a board is created."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        workspace = WorkspaceFactory(owner=user)
        member = UserFactory()
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        WorkspaceMembershipFactory(workspace=workspace, user=member, role='member')
        
        board = BoardFactory(workspace=workspace)
        
        NotificationService.notify_board_created(
            workspace=workspace,
            board=board,
            creator=user
        )
        
        # Only member should receive notification (not creator)
        notification = Notification.objects.filter(
            recipient=member,
            notification_type='workspace'
        ).first()
        
        assert notification is not None
        assert 'New board created' in notification.title
        assert str(board.id) in notification.metadata['board_id']
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_notify_list_created(self, mock_channel_layer, user):
        """Test notifying workspace members when a list is created."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        workspace = WorkspaceFactory(owner=user)
        member = UserFactory()
        WorkspaceMembershipFactory(workspace=workspace, user=user, role='owner')
        WorkspaceMembershipFactory(workspace=workspace, user=member, role='member')
        
        from apps.workspaces.models import BoardList
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='Test List', position=0)
        
        NotificationService.notify_list_created(
            workspace=workspace,
            board=board,
            board_list=board_list,
            creator=user
        )
        
        notification = Notification.objects.filter(
            recipient=member,
            notification_type='workspace'
        ).first()
        
        assert notification is not None
        assert 'New list added' in notification.title
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_notify_card_comment(self, mock_channel_layer, user):
        """Test notifying card assignees about a comment."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        workspace = WorkspaceFactory(owner=user)
        assignee = UserFactory()
        commenter = UserFactory()
        
        from apps.workspaces.models import BoardList, Card
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='Test List', position=0)
        card = Card.objects.create(list=board_list, title='Test Card', position=0)
        card.assignees.add(assignee)
        
        NotificationService.notify_card_comment(
            card=card,
            comment_text='This is a test comment',
            commenter=commenter
        )
        
        notification = Notification.objects.filter(
            recipient=assignee,
            notification_type='comment'
        ).first()
        
        assert notification is not None
        assert 'commented on a card' in notification.title
    
    @patch('apps.notifications.services.get_channel_layer')
    def test_notify_card_comment_with_mentioned_users(self, mock_channel_layer, user):
        """Test notifying mentioned users in a card comment."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_channel_layer.return_value = mock_layer
        
        workspace = WorkspaceFactory(owner=user)
        mentioned_user = UserFactory()
        commenter = UserFactory()
        
        from apps.workspaces.models import BoardList, Card
        board = BoardFactory(workspace=workspace)
        board_list = BoardList.objects.create(board=board, name='Test List', position=0)
        card = Card.objects.create(list=board_list, title='Test Card', position=0)
        
        NotificationService.notify_card_comment(
            card=card,
            comment_text='Hey @mentioned_user check this out',
            commenter=commenter,
            mentioned_users=[mentioned_user]
        )
        
        notification = Notification.objects.filter(
            recipient=mentioned_user,
            notification_type='mention'
        ).first()
        
        assert notification is not None
        assert 'mentioned you' in notification.title
