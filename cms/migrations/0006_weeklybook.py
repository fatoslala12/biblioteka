from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cms", "0005_contactmessage_is_replied_contactmessage_replied_at_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WeeklyBook",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220, verbose_name="Titulli")),
                ("excerpt", models.TextField(blank=True, default="", verbose_name="Përshkrim i shkurtër")),
                ("content", models.TextField(blank=True, default="", verbose_name="Përmbajtje")),
                ("published_at", models.DateTimeField(verbose_name="Publikuar më")),
                ("is_published", models.BooleanField(default=True, verbose_name="Aktiv")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("author", models.CharField(blank=True, default="", max_length=180, verbose_name="Autori")),
                ("image", models.ImageField(blank=True, null=True, upload_to="cms/weekly-books/", verbose_name="Kopertina")),
                ("cta_url", models.CharField(blank=True, default="", max_length=300, verbose_name="Linku (opsional)")),
                ("cta_label", models.CharField(blank=True, default="Shiko më shumë", max_length=50, verbose_name="Teksti i butonit")),
                ("show_on_home", models.BooleanField(default=True, verbose_name="Shfaq në faqen kryesore")),
            ],
            options={
                "verbose_name": "Libri i javës",
                "verbose_name_plural": "Libri i javës",
                "ordering": ("-published_at", "-id"),
            },
        ),
    ]
