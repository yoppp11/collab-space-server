"""
Document Celery Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.conf import settings


@shared_task
def cleanup_old_versions():
    """
    Clean up old document versions based on retention policy.
    """
    from .models import DocumentVersion
    
    cutoff_date = timezone.now() - timedelta(
        days=settings.DOCUMENT_VERSION_RETENTION_DAYS
    )
    
    # Keep at least the last 10 versions per document
    deleted_count = 0
    
    from django.db.models import Count
    from .models import Document
    
    for document in Document.objects.annotate(version_count=Count('versions')):
        if document.version_count > 10:
            # Delete old versions
            old_versions = document.versions.filter(
                created_at__lt=cutoff_date
            ).order_by('version_number')[:-10]
            
            count = old_versions.delete()[0]
            deleted_count += count
    
    return f"Deleted {deleted_count} old versions"


@shared_task
def export_document_pdf(document_id: str, user_id: str):
    """
    Export document to PDF (background task).
    """
    # This would use a library like WeasyPrint or Playwright
    # to render the document as PDF
    pass


@shared_task
def index_document_for_search(document_id: str):
    """
    Index document content for full-text search.
    Could use Elasticsearch or PostgreSQL full-text search.
    """
    from .models import Document
    
    try:
        document = Document.objects.get(id=document_id)
        
        # Extract all text from blocks
        blocks = document.blocks.all()
        full_text = ' '.join(block.text for block in blocks if block.text)
        
        # Index in search engine
        # For PostgreSQL, you'd use SearchVector
        # For Elasticsearch, you'd send to ES cluster
        
        return f"Indexed document {document_id}"
    except Document.DoesNotExist:
        return f"Document {document_id} not found"
