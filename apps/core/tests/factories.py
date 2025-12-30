"""
Factory classes for generating test data using factory_boy.
"""
import factory
from factory.django import DjangoModelFactory
from faker import Faker
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify

User = get_user_model()
fake = Faker()


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
        django_get_or_create = ('email',)
    
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    username = factory.Sequence(lambda n: f'user{n}')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    avatar_color = factory.Faker('hex_color')
    bio = factory.Faker('text', max_nb_chars=200)
    timezone = 'UTC'
    is_active = True
    is_verified = True
    last_seen = factory.LazyFunction(timezone.now)
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password after creation."""
        if not create:
            return
        password = extracted or 'testpass123'
        obj.set_password(password)
        obj.save()


class SuperUserFactory(UserFactory):
    """Factory for creating superuser instances."""
    
    is_staff = True
    is_superuser = True
    is_verified = True


class WorkspaceFactory(DjangoModelFactory):
    """Factory for creating Workspace instances."""
    
    class Meta:
        model = 'workspaces.Workspace'
    
    name = factory.Faker('company')
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name)[:50])
    description = factory.Faker('text', max_nb_chars=200)
    icon = factory.Faker('emoji')
    icon_color = factory.Faker('hex_color')
    owner = factory.SubFactory(UserFactory)
    is_public = False
    settings = factory.Dict({
        'allow_public_pages': False,
        'allow_guests': True,
        'default_page_width': 'full',
    })


class WorkspaceMembershipFactory(DjangoModelFactory):
    """Factory for creating WorkspaceMembership instances."""
    
    class Meta:
        model = 'workspaces.WorkspaceMembership'
    
    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(UserFactory)
    role = 'member'
    is_active = True


class BoardFactory(DjangoModelFactory):
    """Factory for creating Board instances."""
    
    class Meta:
        model = 'workspaces.Board'
    
    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Faker('catch_phrase')
    description = factory.Faker('text', max_nb_chars=200)
    icon = factory.Faker('emoji')
    position = factory.Sequence(lambda n: n * 1000)


class DocumentFactory(DjangoModelFactory):
    """Factory for creating Document instances."""
    
    class Meta:
        model = 'documents.Document'
    
    workspace = factory.SubFactory(WorkspaceFactory)
    title = factory.Faker('sentence', nb_words=4)
    icon = factory.Faker('emoji')
    created_by = factory.SubFactory(UserFactory)
    last_edited_by = factory.SelfAttribute('created_by')
    is_template = False
    is_locked = False
    is_public = False
    tags = factory.List([])
    properties = factory.Dict({})
    current_version = 1


class BlockFactory(DjangoModelFactory):
    """Factory for creating Block instances."""
    
    class Meta:
        model = 'documents.Block'
    
    document = factory.SubFactory(DocumentFactory)
    type = 'text'
    content = factory.Dict({
        'text': factory.Faker('sentence'),
        'format': [],
    })
    parent = None
    position = factory.Sequence(lambda n: n * 1000)


class CommentFactory(DjangoModelFactory):
    """Factory for creating Comment instances."""
    
    class Meta:
        model = 'documents.Comment'
    
    document = factory.SubFactory(DocumentFactory)
    author = factory.SubFactory(UserFactory)
    content = factory.Faker('text', max_nb_chars=500)
    is_resolved = False


class NotificationFactory(DjangoModelFactory):
    """Factory for creating Notification instances."""
    
    class Meta:
        model = 'notifications.Notification'
    
    recipient = factory.SubFactory(UserFactory)
    notification_type = 'mention'
    title = factory.Faker('sentence')
    message = factory.Faker('text', max_nb_chars=200)
    is_read = False


class UserSessionFactory(DjangoModelFactory):
    """Factory for creating UserSession instances."""
    
    class Meta:
        model = 'users.UserSession'
    
    user = factory.SubFactory(UserFactory)
    session_key = factory.Faker('uuid4')
    device_info = factory.Dict({
        'user_agent': factory.Faker('user_agent'),
        'device_type': 'desktop',
    })
    ip_address = factory.Faker('ipv4')
    is_active = True


class UserActivityFactory(DjangoModelFactory):
    """Factory for creating UserActivity instances."""
    
    class Meta:
        model = 'users.UserActivity'
    
    user = factory.SubFactory(UserFactory)
    activity_type = 'login'
    description = factory.Faker('sentence')
    metadata = factory.Dict({})
    ip_address = factory.Faker('ipv4')
