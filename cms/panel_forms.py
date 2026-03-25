from __future__ import annotations

from django import forms
from django.db import transaction

from catalog.models import Author, Book, Copy, CopyCondition, CopyStatus, Genre, Publisher, Tag


def _split_csv(value: str) -> list[str]:
    items = [x.strip() for x in (value or "").split(",")]
    return [x for x in items if x]


class BookPanelForm(forms.ModelForm):
    publisher_name = forms.CharField(required=False, label="Botuesi", help_text="p.sh. OMSC-A")
    authors_csv = forms.CharField(required=False, label="Autorët", help_text="nda me presje, p.sh. Ismail Kadare, ...")
    genres_csv = forms.CharField(required=False, label="Zhanret", help_text="nda me presje, p.sh. Roman, Histori")
    tags_csv = forms.CharField(required=False, label="Tags", help_text="nda me presje, p.sh. klasike, bestseller")

    class Meta:
        model = Book
        fields = ("title", "isbn", "description", "language", "publication_year", "book_type")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].label = "Titulli"
        self.fields["isbn"].label = "ISBN"
        self.fields["description"].label = "Përshkrimi"
        self.fields["language"].label = "Gjuha"
        self.fields["publication_year"].label = "Viti i botimit"
        self.fields["book_type"].label = "Tipi i librit"

        if self.instance and self.instance.pk:
            if self.instance.publisher:
                self.fields["publisher_name"].initial = self.instance.publisher.name
            self.fields["authors_csv"].initial = ", ".join(self.instance.authors.values_list("name", flat=True))
            self.fields["genres_csv"].initial = ", ".join(self.instance.genres.values_list("name", flat=True))
            self.fields["tags_csv"].initial = ", ".join(self.instance.tags.values_list("name", flat=True))

    @transaction.atomic
    def save(self, commit=True):
        book: Book = super().save(commit=False)

        publisher_name = (self.cleaned_data.get("publisher_name") or "").strip()
        if publisher_name:
            publisher, _ = Publisher.objects.get_or_create(name=publisher_name)
            book.publisher = publisher
        else:
            book.publisher = None

        if commit:
            book.save()
            self.save_m2m()

        authors = _split_csv(self.cleaned_data.get("authors_csv") or "")
        genres = _split_csv(self.cleaned_data.get("genres_csv") or "")
        tags = _split_csv(self.cleaned_data.get("tags_csv") or "")

        if book.pk:
            if authors is not None:
                book.authors.set([Author.objects.get_or_create(name=n)[0] for n in authors])
            if genres is not None:
                book.genres.set([Genre.objects.get_or_create(name=n)[0] for n in genres])
            if tags is not None:
                book.tags.set([Tag.objects.get_or_create(name=n)[0] for n in tags])

        return book


class CopyPanelForm(forms.ModelForm):
    class Meta:
        model = Copy
        fields = ("barcode", "status", "location", "shelf", "condition")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["barcode"].label = "Kodi i kopjes (Barcode/QR)"
        self.fields["status"].label = "Statusi"
        self.fields["location"].label = "Lokacioni"
        self.fields["shelf"].label = "Rafti"
        self.fields["condition"].label = "Gjendja"

        self.fields["status"].initial = CopyStatus.AVAILABLE
        self.fields["condition"].initial = CopyCondition.GOOD

