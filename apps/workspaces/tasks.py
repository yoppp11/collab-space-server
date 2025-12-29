"""
Workspace Celery Tasks
"""
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings


@shared_task
def send_workspace_invitation_email(invitation_id: str):
    """
    Send invitation email to invited user.
    """
    from .models import WorkspaceInvitation
    
    try:
        invitation = WorkspaceInvitation.objects.select_related(
            'workspace', 'invited_by'
        ).get(id=invitation_id)
        
        # TODO: Replace with proper email template
        subject = f"You've been invited to join {invitation.workspace.name}"
        message = f"""
        {invitation.invited_by.full_name} has invited you to join the workspace "{invitation.workspace.name}".
        
        {invitation.message if invitation.message else ''}
        
        Click here to accept: {settings.FRONTEND_URL}/invite/{invitation.token}
        
        This invitation expires on {invitation.expires_at.strftime('%Y-%m-%d')}.
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )
        
        return True
    except WorkspaceInvitation.DoesNotExist:
        return False


@shared_task
def expire_old_invitations():
    """
    Mark expired invitations.
    """
    from .models import WorkspaceInvitation
    
    count = WorkspaceInvitation.objects.filter(
        status=WorkspaceInvitation.InvitationStatus.PENDING,
        expires_at__lt=timezone.now()
    ).update(status=WorkspaceInvitation.InvitationStatus.EXPIRED)
    
    return f"Expired {count} invitations"


@shared_task
def generate_activity_reports():
    """
    Generate weekly activity reports for workspaces.
    """
    from .models import Workspace
    
    # Get active workspaces
    workspaces = Workspace.objects.filter(is_deleted=False)
    
    for workspace in workspaces:
        # Generate report logic here
        # This would typically aggregate activity data and send to owners/admins
        pass
    
    return f"Generated reports for {workspaces.count()} workspaces"
