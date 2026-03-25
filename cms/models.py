from django.db import models


class ContactMessage(models.Model):
    """Mesazhet nga faqja e kontaktit."""

    name = models.CharField(max_length=120, verbose_name="Emri")
    email = models.EmailField(verbose_name="Email")
    subject = models.CharField(max_length=160, verbose_name="Subjekti")
    message = models.TextField(verbose_name="Mesazhi")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dërguar më")
    is_read = models.BooleanField(default=False, verbose_name="E lexuar")
    is_replied = models.BooleanField(default=False, verbose_name="U përgjigj")
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name="Përgjigjur më")
    reply_subject = models.CharField(max_length=220, blank=True, default="", verbose_name="Subjekti i përgjigjes")
    reply_body = models.TextField(blank=True, default="", verbose_name="Përgjigja")
    replied_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replied_contact_messages",
        verbose_name="Përgjigjur nga",
    )

    class Meta:
        verbose_name = "Mesazh"
        verbose_name_plural = "Mesazhet"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.subject} — {self.name}"


class PublishableBase(models.Model):
    title = models.CharField(max_length=220, verbose_name="Titulli")
    excerpt = models.TextField(blank=True, default="", verbose_name="Përshkrim i shkurtër")
    content = models.TextField(blank=True, default="", verbose_name="Përmbajtje")
    published_at = models.DateTimeField(verbose_name="Publikuar më")
    is_published = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-published_at", "-id")

    def __str__(self) -> str:
        return self.title


class Announcement(PublishableBase):
    badge = models.CharField(max_length=40, default="Info", blank=True, verbose_name="Etiketa")
    image = models.ImageField(upload_to="cms/announcements/", null=True, blank=True, verbose_name="Foto (opsionale)")
    show_on_home = models.BooleanField(default=True, verbose_name="Shfaq në faqen kryesore")

    class Meta:
        verbose_name = "Njoftim"
        verbose_name_plural = "Njoftime"
        ordering = ("-published_at", "-id")


class Event(PublishableBase):
    location = models.CharField(max_length=180, blank=True, default="", verbose_name="Vendndodhja")
    badge = models.CharField(max_length=40, default="Event", blank=True, verbose_name="Etiketa")
    image = models.ImageField(upload_to="cms/events/", null=True, blank=True, verbose_name="Foto (opsionale)")
    starts_at = models.DateTimeField(null=True, blank=True, verbose_name="Fillon më")
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name="Mbaron më")

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Evente"
        ordering = ("-published_at", "-id")


class Video(PublishableBase):
    video_url = models.URLField(verbose_name="Linku i videos")
    badge = models.CharField(max_length=40, default="Video", blank=True, verbose_name="Etiketa")
    duration = models.CharField(max_length=32, blank=True, default="", verbose_name="Kohëzgjatja")
    image = models.ImageField(upload_to="cms/videos/", null=True, blank=True, verbose_name="Foto (opsionale)")
    show_on_home = models.BooleanField(default=False, verbose_name="Shfaq në faqen kryesore")

    class Meta:
        verbose_name = "Video"
        verbose_name_plural = "Video"
        ordering = ("-published_at", "-id")
