import django_filters

from catalog.models import Book, CopyStatus


class BookFilter(django_filters.FilterSet):
    available = django_filters.BooleanFilter(method="filter_available")

    class Meta:
        model = Book
        fields = {
            "publication_year": ["exact", "gte", "lte"],
            "language": ["exact", "icontains"],
            "book_type": ["exact"],
            "purchase_method": ["exact"],
            "publisher": ["exact"],
            "genres": ["exact"],
            "tags": ["exact"],
            "authors": ["exact"],
        }

    def filter_available(self, queryset, name, value):
        if value is True:
            return queryset.filter(copies__status=CopyStatus.AVAILABLE, copies__is_deleted=False).distinct()
        if value is False:
            return queryset.exclude(copies__status=CopyStatus.AVAILABLE, copies__is_deleted=False).distinct()
        return queryset

