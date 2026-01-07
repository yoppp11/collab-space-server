"""
Notification Services
"""
from typing import Optional
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification

User = get_user_model()


class NotificationService:
    """
    Service for creating and sending notifications.
    """
    
    @staticmethod
    def create_notification(
        recipient,
        notification_type: str,
        title: str,
        message: str,
        actor=None,
        action_url: str = '',
        content_type: str = '',
        object_id: str = None,
        metadata: dict = None
    ) -> Notification:
        """
        Create a notification.
        """
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            actor=actor,
            action_url=action_url,
            content_type=content_type,
            object_id=object_id,
            metadata=metadata or {}
        )
        
        # Send real-time notification via WebSocket
        NotificationService.send_realtime_notification(notification)
        
        return notification
    
    @staticmethod
    def send_realtime_notification(notification: Notification):
        """
        Send notification via WebSocket to connected clients.
        """
        from .serializers import NotificationSerializer
        
        channel_layer = get_channel_layer()
        user_group = f'user_{notification.recipient_id}'
        
        async_to_sync(channel_layer.group_send)(
            user_group,
            {
                'type': 'notification',
                'data': NotificationSerializer(notification).data
            }
        )
    
    @staticmethod
    def notify_mention(mentioned_user, mentioner, document, comment):
        """
        Notify user when mentioned in a comment.
        """
        return NotificationService.create_notification(
            recipient=mentioned_user,
            notification_type=Notification.NotificationType.MENTION,
            title=f"{mentioner.display_name} mentioned you",
            message=f'In "{document.title}": {comment.text[:100]}',
            actor=mentioner,
            action_url=f'/documents/{document.id}#comment-{comment.id}',
            content_type='comment',
            object_id=comment.id
        )
    
    @staticmethod
    def notify_comment(recipient, commenter, document, comment):
        """
        Notify user of a new comment on their document.
        """
        return NotificationService.create_notification(
            recipient=recipient,
            notification_type=Notification.NotificationType.COMMENT,
            title=f"{commenter.display_name} commented",
            message=f'On "{document.title}": {comment.text[:100]}',
            actor=commenter,
            action_url=f'/documents/{document.id}#comment-{comment.id}',
            content_type='comment',
            object_id=comment.id
        )
    
    @staticmethod
    def notify_workspace_member_joined(workspace, new_member, invited_by=None):
        """
        Notify workspace members when a new member joins.
        """
        from apps.workspaces.models import WorkspaceMembership
        
        # Get all active members except the new member
        members = WorkspaceMembership.objects.filter(
            workspace=workspace,
            is_active=True
        ).exclude(user=new_member).select_related('user')
        
        for membership in members:
            NotificationService.create_notification(
                recipient=membership.user,
                notification_type=Notification.NotificationType.WORKSPACE,
                title=f"New member joined {workspace.name}",
                message=f"{new_member.display_name} joined the workspace",
                actor=new_member,
                action_url=f'/dashboard/workspaces/{workspace.id}',
                content_type='workspace',
                object_id=str(workspace.id),
                metadata={
                    'workspace_id': str(workspace.id),
                    'member_id': str(new_member.id),
                    'invited_by_id': str(invited_by.id) if invited_by else None
                }
            )
    
    @staticmethod
    def notify_board_created(workspace, board, creator):
        """
        Notify workspace members when a new board is created.
        """
        from apps.workspaces.models import WorkspaceMembership
        
        # Get all active members except the creator
        members = WorkspaceMembership.objects.filter(
            workspace=workspace,
            is_active=True
        ).exclude(user=creator).select_related('user')
        
        for membership in members:
            NotificationService.create_notification(
                recipient=membership.user,
                notification_type=Notification.NotificationType.WORKSPACE,
                title=f"New board created in {workspace.name}",
                message=f"{creator.display_name} created '{board.name}'",
                actor=creator,
                action_url=f'/dashboard/workspaces/{workspace.id}/boards/{board.id}',
                content_type='board',
                object_id=str(board.id),
                metadata={
                    'workspace_id': str(workspace.id),
                    'board_id': str(board.id)
                }
            )

    @staticmethod
    def notify_list_created(workspace, board, board_list, creator):
        """
        Notify workspace members when a new list is added to a board.
        """
        from apps.workspaces.models import WorkspaceMembership
        
        # Get all active members except the creator
        members = WorkspaceMembership.objects.filter(
            workspace=workspace,
            is_active=True
        ).exclude(user=creator).select_related('user')
        
        for membership in members:
            NotificationService.create_notification(
                recipient=membership.user,
                notification_type=Notification.NotificationType.WORKSPACE,
                title=f"New list added to {board.name}",
                message=f"{creator.display_name} created list '{board_list.name}'",
                actor=creator,
                action_url=f'/dashboard/workspaces/{workspace.id}/boards/{board.id}',
                content_type='board_list',
                object_id=str(board_list.id),
                metadata={
                    'workspace_id': str(workspace.id),
                    'board_id': str(board.id),
                    'list_id': str(board_list.id)
                }
            )
    
    @staticmethod
    def notify_card_comment(card, comment_text, commenter, mentioned_users=None):
        """
        Notify card assignees and mentioned users about a new comment.
        """
        from apps.workspaces.models import Card
        
        # Notify all assignees except the commenter
        assignees = card.assignees.exclude(id=commenter.id)
        for assignee in assignees:
            NotificationService.create_notification(
                recipient=assignee,
                notification_type=Notification.NotificationType.COMMENT,
                title=f"{commenter.display_name} commented on a card",
                message=f'On "{card.title}": {comment_text[:100]}',
                actor=commenter,
                action_url=f'/dashboard/workspaces/{card.list.board.workspace_id}/boards/{card.list.board_id}',
                content_type='card_comment',
                object_id=str(card.id),
                metadata={
                    'card_id': str(card.id),
                    'board_id': str(card.list.board_id)
                }
            )
        
        # Notify mentioned users
        if mentioned_users:
            for mentioned_user in mentioned_users:
                if mentioned_user.id != commenter.id:
                    NotificationService.create_notification(
                        recipient=mentioned_user,
                        notification_type=Notification.NotificationType.MENTION,
                        title=f"{commenter.display_name} mentioned you",
                        message=f'In card "{card.title}": {comment_text[:100]}',
                        actor=commenter,
                        action_url=f'/dashboard/workspaces/{card.list.board.workspace_id}/boards/{card.list.board_id}',
                        content_type='card_comment',
                        object_id=str(card.id),
                        metadata={
                            'card_id': str(card.id),
                            'board_id': str(card.list.board_id)
                        }
                    )
