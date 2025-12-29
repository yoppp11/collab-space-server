"""
Custom Pagination Classes
"""
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response


class StandardResultsPagination(PageNumberPagination):
    """
    Standard pagination for most API endpoints.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'page_size': self.page_size,
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
            }
        })


class CursorResultsPagination(CursorPagination):
    """
    Cursor-based pagination for real-time data that changes frequently.
    Better for infinite scroll and real-time feeds.
    """
    page_size = 20
    ordering = '-created_at'
    cursor_query_param = 'cursor'

    def get_paginated_response(self, data):
        return Response({
            'success': True,
            'data': data,
            'pagination': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
            }
        })


class BlockPagination(CursorPagination):
    """
    Specialized pagination for block content.
    """
    page_size = 50
    ordering = 'position'
    cursor_query_param = 'cursor'
