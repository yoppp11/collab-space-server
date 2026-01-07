"""
Cache Management API Views
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from apps.core.cache import CacheManager, get_cache_stats, clear_all_cache


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def cache_stats(request):
    """
    Get Redis cache statistics.
    Admin only endpoint.
    """
    stats = get_cache_stats()
    
    return Response({
        'success': True,
        'data': stats
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def clear_cache(request):
    """
    Clear all cache.
    Admin only endpoint - use with caution!
    """
    cache_type = request.data.get('type', 'all')
    
    if cache_type == 'all':
        clear_all_cache()
        message = "All cache cleared"
    elif cache_type == 'user':
        user_id = request.data.get('user_id')
        if user_id:
            CacheManager.invalidate_user_all(user_id)
            message = f"User {user_id} cache cleared"
        else:
            return Response({
                'success': False,
                'error': {'message': 'user_id required for user cache clear'}
            }, status=status.HTTP_400_BAD_REQUEST)
    elif cache_type == 'workspace':
        workspace_id = request.data.get('workspace_id')
        if workspace_id:
            CacheManager.invalidate_workspace_all(workspace_id)
            message = f"Workspace {workspace_id} cache cleared"
        else:
            return Response({
                'success': False,
                'error': {'message': 'workspace_id required for workspace cache clear'}
            }, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response({
            'success': False,
            'error': {'message': f'Unknown cache type: {cache_type}'}
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': True,
        'message': message
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def invalidate_my_cache(request):
    """
    Invalidate current user's cache.
    Useful when user wants to force refresh.
    """
    CacheManager.invalidate_user_all(str(request.user.id))
    
    return Response({
        'success': True,
        'message': 'Your cache has been cleared'
    })
