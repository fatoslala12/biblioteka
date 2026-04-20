from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_alter_author_options_alter_book_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="book",
            name="price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name="Çmimi"),
        ),
        migrations.AddField(
            model_name="book",
            name="purchase_method",
            field=models.CharField(
                choices=[
                    ("DONATION", "Donacion"),
                    ("GIFT", "Dhuratë"),
                    ("FULL_PRICE", "Blerje me çmim të plotë"),
                    ("DISCOUNTED", "Blerje me ulje"),
                    ("EXCHANGE", "Shkëmbim"),
                    ("OTHER", "Tjetër"),
                ],
                default="FULL_PRICE",
                max_length=20,
                verbose_name="Mënyra e blerjes",
            ),
        ),
        migrations.AddField(
            model_name="book",
            name="purchase_place",
            field=models.CharField(blank=True, default="", max_length=180, verbose_name="Vendi i blerjes"),
        ),
    ]
