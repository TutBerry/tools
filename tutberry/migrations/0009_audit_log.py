from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("tutberry", "0008_outbox")]
    operations = [migrations.CreateModel(name="AuditRecord", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("actor_id", models.UUIDField()),
        ("object_id", models.UUIDField()),
        ("action", models.CharField(max_length=80)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
    ])]
