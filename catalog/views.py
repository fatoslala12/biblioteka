from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import IsNotLocked, IsStaffOrAdmin
from catalog.filters import BookFilter
from catalog.models import Book, Copy
from catalog.serializers import BookSerializer, CopySerializer


class BookViewSet(ReadOnlyModelViewSet):
    """
    Public catalog endpoint (MVP): list/retrieve only.
    """

    permission_classes = [AllowAny]
    serializer_class = BookSerializer
    queryset = (
        Book.objects.filter(is_deleted=False)
        .select_related("publisher")
        .prefetch_related("authors", "genres", "tags", "copies")
        .order_by("title")
    )
    filterset_class = BookFilter
    search_fields = ("title", "isbn", "authors__name", "copies__barcode")
    ordering_fields = ("title", "publication_year", "created_at")


class CopyViewSet(ModelViewSet):
    """
    Staff/admin endpoint for inventory management.
    """

    permission_classes = [IsStaffOrAdmin, IsNotLocked]
    serializer_class = CopySerializer
    queryset = Copy.objects.select_related("book").filter(is_deleted=False).order_by("-created_at")
    filterset_fields = ("status", "condition", "location", "shelf", "book")
    search_fields = ("barcode", "book__title", "book__isbn")
    ordering_fields = ("created_at", "barcode", "status")
