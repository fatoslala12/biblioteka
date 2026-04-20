from rest_framework import serializers

from .models import Author, Book, Copy, Genre, Publisher, Tag


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ("id", "name")


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name")


class PublisherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = ("id", "name")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id", "name")


class BookSerializer(serializers.ModelSerializer):
    authors = AuthorSerializer(many=True, read_only=True)
    genres = GenreSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    publisher = PublisherSerializer(read_only=True)

    total_copies = serializers.SerializerMethodField()
    available_copies = serializers.SerializerMethodField()
    on_loan_copies = serializers.SerializerMethodField()
    on_hold_copies = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "isbn",
            "description",
            "cover_image",
            "language",
            "publication_year",
            "book_type",
            "is_recommended",
            "price",
            "purchase_method",
            "purchase_place",
            "publisher",
            "authors",
            "genres",
            "tags",
            "total_copies",
            "available_copies",
            "on_loan_copies",
            "on_hold_copies",
        )

    def _copies_qs(self, obj: Book):
        return obj.copies.filter(is_deleted=False)

    def get_total_copies(self, obj: Book) -> int:
        return self._copies_qs(obj).count()

    def get_available_copies(self, obj: Book) -> int:
        return self._copies_qs(obj).filter(status="AVAILABLE").count()

    def get_on_loan_copies(self, obj: Book) -> int:
        return self._copies_qs(obj).filter(status="ON_LOAN").count()

    def get_on_hold_copies(self, obj: Book) -> int:
        return self._copies_qs(obj).filter(status="ON_HOLD").count()


class CopySerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)

    class Meta:
        model = Copy
        fields = (
            "id",
            "book",
            "book_title",
            "barcode",
            "status",
            "location",
            "shelf",
            "condition",
            "hold_for",
            "hold_expires_at",
        )
