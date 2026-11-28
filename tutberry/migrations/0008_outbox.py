from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("tutberry", "0007_listing_search_fields")]
    operations = [migrations.CreateModel(name="OutboxRecord", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("event_id", models.CharField(max_length=36, unique=True)),
        ("routing_key", models.CharField(max_length=80)),
        ("payload", models.JSONField()),
        ("headers", models.JSONField(default=dict)),
        ("published_at", models.DateTimeField(null=True)),
        ("created_at", models.DateTimeField(auto_now_add=True)),
    ], options={"indexes": [models.Index(fields=["id"], condition=models.Q(published_at__isnull=True), name="outbox_unpublished_idx")]})]
