"""
Custom User Model for Real-time Collaboration Platform
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from apps.core.models import BaseModel, SoftDeleteModel, SoftDeleteManager


class UserManager(BaseUserManager, SoftDeleteManager):
    """
    Custom user manager that handles email as the unique identifier.
    """
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError('Users must have an email address')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel, SoftDeleteModel):
    """
    Custom User model using email as the unique identifier.
    """
    
    email = models.EmailField(
        max_length=255,
        unique=True,
        db_index=True,
        verbose_name='Email Address'
    )
    username = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        blank=True,
        null=True
    )
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    
    # Profile fields
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        blank=True,
        null=True
    )
    avatar_color = models.CharField(
        max_length=7,
        default='#6366f1',
        help_text='Hex color for avatar background when no image'
    )
    bio = models.TextField(max_length=500, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Status fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Tracking
    last_seen = models.DateTimeField(null=True, blank=True)
    
    # Settings stored as JSONB for flexibility
    preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text='User preferences and settings'
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['is_active', 'is_deleted']),
            models.Index(fields=['last_seen']),
        ]
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip() or self.email.split('@')[0]
    
    @property
    def display_name(self):
        """Return the best display name available."""
        if self.username:
            return self.username
        return self.full_name
    
    @property
    def initials(self):
        """Return user initials for avatar fallback."""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        return self.email[0:2].upper()


class UserSession(BaseModel):
    """
    Track active user sessions for real-time presence and security.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    session_key = models.CharField(max_length=255, unique=True)
    device_info = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'user_sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.session_key[:8]}"


class UserActivity(BaseModel):
    """
    Audit log for user activities across the platform.
    """
    
    class ActivityType(models.TextChoices):
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        PASSWORD_CHANGE = 'password_change', 'Password Change'
        PROFILE_UPDATE = 'profile_update', 'Profile Update'
        WORKSPACE_CREATE = 'workspace_create', 'Workspace Create'
        WORKSPACE_JOIN = 'workspace_join', 'Workspace Join'
        DOCUMENT_CREATE = 'document_create', 'Document Create'
        DOCUMENT_EDIT = 'document_edit', 'Document Edit'
        DOCUMENT_DELETE = 'document_delete', 'Document Delete'
        COMMENT_CREATE = 'comment_create', 'Comment Create'
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activities'
    )
    activity_type = models.CharField(
        max_length=50,
        choices=ActivityType.choices,
        db_index=True
    )
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Reference to related objects
    content_type = models.CharField(max_length=100, blank=True)
    object_id = models.UUIDField(null=True, blank=True, db_index=True)
    
    class Meta:
        db_table = 'user_activities'
        verbose_name_plural = 'User Activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.activity_type}"
