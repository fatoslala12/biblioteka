from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Author(TimestampedModel):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Autor"
        verbose_name_plural = "Autorë"


class Genre(TimestampedModel):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Zhanër"
        verbose_name_plural = "Zhanre"


class Publisher(TimestampedModel):
    name = models.CharField(max_length=200, unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Botues"
        verbose_name_plural = "Botues"


class Tag(TimestampedModel):
    name = models.CharField(max_length=64, unique=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name = "Etiketë"
        verbose_name_plural = "Etiketa"


class BookType(models.TextChoices):
    GENERAL = "GENERAL", "I përgjithshëm"
    REFERENCE = "REFERENCE", "Referencë (vetëm në bibliotekë)"


class PurchaseMethod(models.TextChoices):
    DONATION = "DONATION", "Donacion"
    GIFT = "GIFT", "Dhuratë"
    FULL_PRICE = "FULL_PRICE", "Blerje me çmim të plotë"
    DISCOUNTED = "DISCOUNTED", "Blerje me ulje"
    EXCHANGE = "EXCHANGE", "Shkëmbim"
    OTHER = "OTHER", "Tjetër"


class Book(TimestampedModel):
    title = models.CharField(max_length=255)
    isbn = models.CharField(max_length=32, blank=True, default="")
    description = models.TextField(blank=True, default="")
    cover_image = models.ImageField(upload_to="catalog/books/covers/", null=True, blank=True, verbose_name="Foto kopertine")
    language = models.CharField(max_length=64, blank=True, default="")
    publication_year = models.PositiveIntegerField(null=True, blank=True)
    book_type = models.CharField(max_length=16, choices=BookType.choices, default=BookType.GENERAL)
    is_recommended = models.BooleanField(default=False, verbose_name="Shto te librat e rekomanduar")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Çmimi")
    purchase_method = models.CharField(
        max_length=20,
        choices=PurchaseMethod.choices,
        default=PurchaseMethod.FULL_PRICE,
        verbose_name="Mënyra e blerjes",
    )
    purchase_place = models.CharField(max_length=180, blank=True, default="", verbose_name="Vendi i blerjes")

    publisher = models.ForeignKey(Publisher, null=True, blank=True, on_delete=models.SET_NULL, related_name="books")
    authors = models.ManyToManyField(Author, blank=True, related_name="books")
    genres = models.ManyToManyField(Genre, blank=True, related_name="books")
    tags = models.ManyToManyField(Tag, blank=True, related_name="books")

    is_deleted = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.title

    class Meta:
        verbose_name = "Libër"
        verbose_name_plural = "Libra"


class CopyStatus(models.TextChoices):
    AVAILABLE = "AVAILABLE", "Disponueshme"
    ON_LOAN = "ON_LOAN", "Në huazim"
    ON_HOLD = "ON_HOLD", "Në pritje për marrje"
    LOST = "LOST", "Humbur"
    DAMAGED = "DAMAGED", "Dëmtuar"
    IN_PROCESSING = "IN_PROCESSING", "Në përpunim"


class CopyCondition(models.TextChoices):
    GOOD = "GOOD", "E mirë"
    FAIR = "FAIR", "Mesatare"
    POOR = "POOR", "E dobët"


class Copy(TimestampedModel):
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="copies")
    barcode = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=CopyStatus.choices, default=CopyStatus.AVAILABLE)

    location = models.CharField(max_length=120, blank=True, default="")
    shelf = models.CharField(max_length=120, blank=True, default="")
    condition = models.CharField(max_length=12, choices=CopyCondition.choices, default=CopyCondition.GOOD)

    hold_for = models.ForeignKey(
        "accounts.MemberProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="holds_for_copies",
    )
    hold_expires_at = models.DateTimeField(null=True, blank=True)

    is_deleted = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.barcode} - {self.book.title}"

    class Meta:
        verbose_name = "Kopje"
        verbose_name_plural = "Kopje"
