from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_book_acquisition_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="book",
            name="cover_image",
            field=models.ImageField(blank=True, null=True, upload_to="catalog/books/covers/", verbose_name="Foto kopertine"),
        ),
        migrations.AddField(
            model_name="book",
            name="is_recommended",
            field=models.BooleanField(default=False, verbose_name="Shto te librat e rekomanduar"),
        ),
    ]
