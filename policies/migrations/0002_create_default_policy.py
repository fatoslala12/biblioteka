from django.db import migrations


def create_default_policy(apps, schema_editor):
    LibraryPolicy = apps.get_model("policies", "LibraryPolicy")
    LibraryPolicy.objects.get_or_create(name="default")


class Migration(migrations.Migration):
    dependencies = [
        ("policies", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_policy, migrations.RunPython.noop),
    ]

