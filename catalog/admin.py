from django.contrib import admin
from django.db.models import Count, Q
from django.http import HttpRequest, JsonResponse
from django.urls import path
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.safestring import mark_safe

from .models import Author, Book, Copy, CopyStatus, Genre, Publisher, Tag
from circulation.models import Loan


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    change_form_template = "admin/catalog/book/change_form.html"
    change_list_template = "admin/catalog/book/change_list.html"

    class AuthorFilter(admin.SimpleListFilter):
        title = "Autori"
        parameter_name = "author_id"

        def lookups(self, request, model_admin):
            return [(str(a.id), a.name) for a in Author.objects.order_by("name")]

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(authors__id=self.value())
            return queryset

    class PublisherFilter(admin.SimpleListFilter):
        title = "Shtëpia botuese"
        parameter_name = "publisher_id"

        def lookups(self, request, model_admin):
            return [(str(p.id), p.name) for p in Publisher.objects.order_by("name")]

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(publisher_id=self.value())
            return queryset

    class PublicationYearFilter(admin.SimpleListFilter):
        title = "Viti"
        parameter_name = "pub_year"

        def lookups(self, request, model_admin):
            years = (
                Book.objects.exclude(publication_year__isnull=True)
                .values_list("publication_year", flat=True)
                .distinct()
                .order_by("-publication_year")
            )
            return [(str(y), str(y)) for y in years]

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(publication_year=self.value())
            return queryset

    class GenreFilter(admin.SimpleListFilter):
        title = "Zhanri"
        parameter_name = "genre_id"

        def lookups(self, request, model_admin):
            return [(str(g.id), g.name) for g in Genre.objects.order_by("name")]

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(genres__id=self.value())
            return queryset

    list_display = (
        "cover_preview",
        "title_display",
        "author_display",
        "isbn_display",
        "publication_year_display",
        "book_type_display",
        "is_recommended",
        "purchase_method_display",
        "price_display",
        "publisher_display",
        "total_copies",
        "available_copies",
    )
    list_filter = (AuthorFilter, PublisherFilter, PublicationYearFilter, GenreFilter, "purchase_method", "is_recommended")
    search_fields = ("title", "isbn", "publisher__name", "authors__name")
    autocomplete_fields = ("publisher", "authors", "genres", "tags")
    actions = None

    def get_urls(self):
        from catalog.import_views import book_import, book_import_sample

        urls = super().get_urls()
        custom = [
            path("quick-create-related/", self.admin_site.admin_view(self.quick_create_related), name="catalog_book_quick_create_related"),
            path("import/", self.admin_site.admin_view(book_import), name="catalog_book_import"),
            path("import-sample/", self.admin_site.admin_view(book_import_sample), name="catalog_book_import_sample"),
        ]
        return custom + urls

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        # Add stats/history at the end in change form
        if obj is not None:
            if "borrow_count" not in fields:
                fields.append("borrow_count")
            if "borrow_history" not in fields:
                fields.append("borrow_history")
        return fields

    def get_fieldsets(self, request, obj=None):
        base = (
            (
                "Informacion bazë",
                {
                    "fields": (
                        "title",
                        "isbn",
                        "cover_image",
                        "is_recommended",
                        "description",
                        ("language", "publication_year"),
                    )
                },
            ),
            (
                "Blerja",
                {
                    "fields": (
                        ("price", "purchase_method"),
                        "purchase_place",
                    )
                },
            ),
            (
                "Klasifikim",
                {
                    "fields": (
                        "book_type",
                        "publisher",
                        "authors",
                        "genres",
                        "tags",
                    )
                },
            ),
        )
        if obj is None:
            return base
        return base + (
            (
                "Statistika dhe historiku",
                {"fields": ("borrow_count", "borrow_history")},
            ),
        )

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("publisher").prefetch_related("authors")
        return qs.annotate(
            _total_copies=Count("copies", filter=Q(copies__is_deleted=False), distinct=True),
            _available_copies=Count(
                "copies",
                filter=Q(copies__is_deleted=False, copies__status=CopyStatus.AVAILABLE),
                distinct=True,
            ),
        )

    @admin.display(description="Titulli", ordering="title")
    def title_display(self, obj: Book):
        return obj.title

    @admin.display(description="Kopertina")
    def cover_preview(self, obj: Book):
        if not obj.cover_image:
            return "—"
        return format_html(
            '<img src="{}" style="width:38px;height:54px;border-radius:8px;object-fit:cover;border:1px solid rgba(15,23,42,.12);" />',
            obj.cover_image.url,
        )

    @admin.display(description="Autori")
    def author_display(self, obj: Book):
        all_authors = list(obj.authors.all())
        names = [a.name for a in all_authors[:2]]
        if not names:
            return "—"
        if len(all_authors) > 2:
            return f"{', '.join(names)} +{len(all_authors) - 2}"
        return ", ".join(names)

    @admin.display(description="ISBN", ordering="isbn")
    def isbn_display(self, obj: Book):
        return obj.isbn or "—"

    @admin.display(description="Viti", ordering="publication_year")
    def publication_year_display(self, obj: Book):
        return obj.publication_year or "—"

    @admin.display(description="Lloji", ordering="book_type")
    def book_type_display(self, obj: Book):
        return obj.get_book_type_display() if obj.book_type else "—"

    @admin.display(description="Mënyra e blerjes", ordering="purchase_method")
    def purchase_method_display(self, obj: Book):
        return obj.get_purchase_method_display() if obj.purchase_method else "—"

    @admin.display(description="Çmimi", ordering="price")
    def price_display(self, obj: Book):
        return f"{obj.price:.2f}" if obj.price is not None else "—"

    @admin.display(description="Botuesi", ordering="publisher__name")
    def publisher_display(self, obj: Book):
        return obj.publisher.name if obj.publisher_id else "—"

    @admin.display(description="Kopje totale", ordering="_total_copies")
    def total_copies(self, obj: Book) -> int:
        return getattr(obj, "_total_copies", 0)

    @admin.display(description="Kopje të lira", ordering="_available_copies")
    def available_copies(self, obj: Book) -> int:
        return getattr(obj, "_available_copies", 0)

    @admin.display(description="Marrë hua (total)")
    def borrow_count(self, obj: Book) -> str:
        n = Loan.objects.filter(copy__book=obj).count()
        q = urlencode({"copy__book__id__exact": str(obj.id), "loan_status": "ALL", "loan_source": "ALL"})
        return format_html('<a href="{}">{}</a>', f"/admin/circulation/loan/?{q}", n)

    @admin.display(description="Historiku i huazimeve (20 të fundit)")
    def borrow_history(self, obj: Book) -> str:
        return self._borrow_history_html(obj, "ALL")

    def _borrow_history_html(self, obj: Book, scope: str = "ALL") -> str:
        scope = (scope or "ALL").upper()
        if scope not in {"ALL", "ACTIVE", "RETURNED"}:
            scope = "ALL"
        qs = (
            Loan.objects.select_related("member", "member__user", "copy")
            .filter(copy__book=obj)
            .order_by("-loaned_at")
        )
        if scope == "ACTIVE":
            qs = qs.filter(status="ACTIVE")
        elif scope == "RETURNED":
            qs = qs.filter(status="RETURNED")
        qs = qs[:20]
        if not qs:
            return "—"
        rows = []
        for l in qs:
            m = l.member
            name = (m.full_name or "").strip() or (m.user.get_full_name().strip() if m.user_id else "") or m.member_no
            nid = (m.national_id or "").strip()
            member_url = f"/admin/accounts/memberprofile/{m.id}/change/"
            rows.append(
                f"<tr>"
                f"<td><a href='{member_url}' style='font-weight:900;'>{name}</a><div style='font-size:11px; opacity:.75;'>"
                f"{m.member_no}{(' • ' + nid) if nid else ''}</div></td>"
                f"<td>{l.copy.barcode}</td>"
                f"<td>{l.loaned_at:%Y-%m-%d}</td>"
                f"<td>{l.due_at:%Y-%m-%d}</td>"
                f"<td>{(l.returned_at.strftime('%Y-%m-%d') if l.returned_at else '—')}</td>"
                f"</tr>"
            )
        hist_all = f"/admin/catalog/book/{obj.id}/change/?{urlencode({'history_scope': 'ALL'})}"
        hist_active = f"/admin/catalog/book/{obj.id}/change/?{urlencode({'history_scope': 'ACTIVE'})}"
        hist_returned = f"/admin/catalog/book/{obj.id}/change/?{urlencode({'history_scope': 'RETURNED'})}"
        all_cls = "btn btn-xs " + ("btn-primary" if scope == "ALL" else "btn-outline-secondary")
        active_cls = "btn btn-xs " + ("btn-primary" if scope == "ACTIVE" else "btn-outline-secondary")
        returned_cls = "btn btn-xs " + ("btn-primary" if scope == "RETURNED" else "btn-outline-secondary")
        return format_html(
            "<div style='overflow:auto; max-height: 320px;'>"
            "<div style='display:flex; gap:8px; align-items:center; margin-bottom:10px;'>"
            "<a class='{}' href='{}'>Të gjitha</a>"
            "<a class='{}' href='{}'>Aktive</a>"
            "<a class='{}' href='{}'>Të kthyera</a>"
            "</div>"
            "<table class='table table-sm'>"
            "<thead><tr>"
            "<th>Anëtari</th><th>Kopja</th><th>Marrë</th><th>Afati</th><th>Kthyer</th>"
            "</tr></thead>"
            "<tbody>{}</tbody></table></div>",
            all_cls,
            hist_all,
            active_cls,
            hist_active,
            returned_cls,
            hist_returned,
            mark_safe("".join(rows)),
        )

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["sl_quick_related_api_url"] = "/admin/catalog/book/quick-create-related/"
        if object_id:
            book = self.get_object(request, object_id)
            if book:
                history_scope = (request.GET.get("history_scope") or "ALL").upper()
                if history_scope not in {"ALL", "ACTIVE", "RETURNED"}:
                    history_scope = "ALL"
                loan_status = history_scope if history_scope in {"ACTIVE", "RETURNED"} else "ALL"
                book_loans_qs = {"copy__book__id__exact": str(book.id), "loan_status": loan_status, "loan_source": "ALL"}
                extra_context["sl_book"] = book
                extra_context["sl_book_total_loans"] = Loan.objects.filter(copy__book=book).count()
                extra_context["sl_book_active_loans"] = Loan.objects.filter(copy__book=book, status="ACTIVE").count()
                extra_context["sl_book_total_copies"] = book.copies.filter(is_deleted=False).count()
                extra_context["sl_book_available_copies"] = book.copies.filter(
                    is_deleted=False, status=CopyStatus.AVAILABLE
                ).count()
                extra_context["sl_borrow_count_html"] = self.borrow_count(book)
                extra_context["sl_borrow_history_html"] = self._borrow_history_html(book, history_scope)
                extra_context["sl_book_history_list_url"] = f"/admin/circulation/loan/?{urlencode(book_loans_qs)}"
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)

    def quick_create_related(self, request: HttpRequest):
        if request.method != "POST":
            return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)
        kind = (request.POST.get("kind") or "").strip().lower()
        name = (request.POST.get("name") or "").strip()
        if kind not in {"author", "genre", "tag", "publisher"}:
            return JsonResponse({"ok": False, "error": "Lloj i pavlefshëm."}, status=400)
        if not name:
            return JsonResponse({"ok": False, "error": "Vendos emrin."}, status=400)

        if kind == "author":
            obj = Author.objects.filter(name__iexact=name).first() or Author.objects.create(name=name)
            return JsonResponse({"ok": True, "id": obj.id, "label": obj.name})
        if kind == "genre":
            obj, _ = Genre.objects.get_or_create(name=name)
            return JsonResponse({"ok": True, "id": obj.id, "label": obj.name})
        if kind == "tag":
            obj, _ = Tag.objects.get_or_create(name=name)
            return JsonResponse({"ok": True, "id": obj.id, "label": obj.name})

        obj, _ = Publisher.objects.get_or_create(name=name)
        return JsonResponse({"ok": True, "id": obj.id, "label": obj.name})


BookAdmin.readonly_fields = getattr(BookAdmin, "readonly_fields", tuple()) + ("borrow_count", "borrow_history")


class CopyInline(admin.TabularInline):
    model = Copy
    extra = 0
    fields = ("barcode", "status", "location", "shelf", "condition", "hold_for", "hold_expires_at", "is_deleted")
    readonly_fields = ("hold_for", "hold_expires_at")


BookAdmin.inlines = [CopyInline]


@admin.register(Copy)
class CopyAdmin(admin.ModelAdmin):
    list_display = ("barcode", "book", "status", "location", "shelf", "condition", "hold_for", "hold_expires_at")
    list_filter = ("status", "condition")
    search_fields = ("barcode", "book__title", "book__isbn")
