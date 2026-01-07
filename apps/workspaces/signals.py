"""
Workspace Signals
"""
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import WorkspaceMembership, Board, Card, CardComment
from .permissions import invalidate_permission_cache


@receiver(post_save, sender=WorkspaceMembership)
def membership_saved(sender, instance, created, **kwargs):
    """
    Invalidate permission cache when membership changes.
    Broadcast member join/role update to workspace.
    """
    invalidate_permission_cache(
        user_id=instance.user_id,
        workspace_id=instance.workspace_id
    )
    
    if created:
        # Broadcast member joined event
        from .serializers import WorkspaceMembershipSerializer
        channel_layer = get_channel_layer()
        workspace_group = f'workspace_{instance.workspace_id}'
        
        async_to_sync(channel_layer.group_send)(
            workspace_group,
            {
                'type': 'member.joined',
                'data': {
                    'membership': WorkspaceMembershipSerializer(instance).data,
                    'user': {
                        'id': str(instance.user.id),
                        'email': instance.user.email,
                        'display_name': instance.user.display_name,
                    }
                }
            }
        )


@receiver(post_delete, sender=WorkspaceMembership)
def membership_deleted(sender, instance, **kwargs):
    """
    Invalidate permission cache when membership is deleted.
    Broadcast member left event.
    """
    invalidate_permission_cache(
        user_id=instance.user_id,
        workspace_id=instance.workspace_id
    )
    
    # Broadcast member left event
    channel_layer = get_channel_layer()
    workspace_group = f'workspace_{instance.workspace_id}'
    
    async_to_sync(channel_layer.group_send)(
        workspace_group,
        {
            'type': 'member.left',
            'data': {
                'user_id': str(instance.user_id),
                'workspace_id': str(instance.workspace_id)
            }
        }
    )


@receiver(post_save, sender=Board)
def board_saved(sender, instance, created, **kwargs):
    """
    Broadcast board creation/update to workspace members.
    """
    from .serializers import BoardSerializer
    
    channel_layer = get_channel_layer()
    workspace_group = f'workspace_{instance.workspace_id}'
    
    if created:
        async_to_sync(channel_layer.group_send)(
            workspace_group,
            {
                'type': 'board.created',
                'data': BoardSerializer(instance).data
            }
        )
    else:
        async_to_sync(channel_layer.group_send)(
            workspace_group,
            {
                'type': 'board.updated',
                'data': BoardSerializer(instance).data
            }
        )


@receiver(post_delete, sender=Board)
def board_deleted(sender, instance, **kwargs):
    """
    Broadcast board deletion to workspace members.
    """
    channel_layer = get_channel_layer()
    workspace_group = f'workspace_{instance.workspace_id}'
    
    async_to_sync(channel_layer.group_send)(
        workspace_group,
        {
            'type': 'board.deleted',
            'data': {
                'board_id': str(instance.id),
                'workspace_id': str(instance.workspace_id)
            }
        }
    )


@receiver(post_save, sender=Card)
def card_saved(sender, instance, created, **kwargs):
    """
    Broadcast card creation/update to workspace members.
    """
    from .serializers import CardSerializer
    
    # Get workspace_id through the board list's board
    workspace_id = instance.list.board.workspace_id
    
    channel_layer = get_channel_layer()
    workspace_group = f'workspace_{workspace_id}'
    
    if created:
        async_to_sync(channel_layer.group_send)(
            workspace_group,
            {
                'type': 'card.created',
                'data': CardSerializer(instance).data
            }
        )
    else:
        async_to_sync(channel_layer.group_send)(
            workspace_group,
            {
                'type': 'card.updated',
                'data': CardSerializer(instance).data
            }
        )


@receiver(post_save, sender=CardComment)
def card_comment_saved(sender, instance, created, **kwargs):
    """
    Broadcast card comment creation to workspace members.
    """
    if created:
        from .serializers import CardCommentSerializer
        
        # Get workspace_id through the card's board
        workspace_id = instance.card.list.board.workspace_id
        
        channel_layer = get_channel_layer()
        workspace_group = f'workspace_{workspace_id}'
        
        async_to_sync(channel_layer.group_send)(
            workspace_group,
            {
                'type': 'card.comment_created',
                'data': CardCommentSerializer(instance).data
            }
        )


@receiver(m2m_changed, sender=CardComment.mentions.through)
def card_comment_mentions_changed(sender, instance, action, pk_set, **kwargs):
    """
    Send notifications when users are mentioned in card comments.
    """
    if action == 'post_add' and pk_set:
        from django.contrib.auth import get_user_model
        from apps.notifications.services import NotificationService
        
        User = get_user_model()
        mentioned_users = User.objects.filter(id__in=pk_set)
        
        NotificationService.notify_card_comment(
            card=instance.card,
            comment_text=instance.text,
            commenter=instance.author,
            mentioned_users=mentioned_users
        )
