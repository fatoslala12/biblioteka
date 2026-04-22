from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_alter_memberprofile_member_no"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="accepted_terms_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="accepted_terms_version",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]

