from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("icfes_dashboard", "0006_add_palancas_narrative"),
    ]

    operations = [
        migrations.CreateModel(
            name="RailwayTrafficLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_id", models.CharField(max_length=64, unique=True)),
                ("timestamp", models.DateTimeField(db_index=True)),
                ("method", models.CharField(blank=True, default="", max_length=12)),
                ("path", models.TextField(db_index=True)),
                ("host", models.CharField(blank=True, default="", max_length=255)),
                ("http_status", models.IntegerField(db_index=True)),
                ("total_duration_ms", models.IntegerField(blank=True, null=True)),
                ("upstream_rq_duration_ms", models.IntegerField(blank=True, null=True)),
                ("tx_bytes", models.BigIntegerField(blank=True, null=True)),
                ("rx_bytes", models.BigIntegerField(blank=True, null=True)),
                ("client_ua", models.TextField(blank=True, default="")),
                ("src_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("edge_region", models.CharField(blank=True, default="", max_length=64)),
                ("upstream_errors", models.TextField(blank=True, default="")),
                (
                    "bot_category",
                    models.CharField(
                        choices=[
                            ("human_or_other", "Human/Other"),
                            ("seo_bot", "SEO Bot"),
                            ("ai_bot", "AI Bot"),
                            ("social_bot", "Social Bot"),
                            ("other_bot", "Other Bot"),
                            ("unknown", "Unknown"),
                        ],
                        db_index=True,
                        default="unknown",
                        max_length=24,
                    ),
                ),
                ("school_slug", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("utm_source", models.CharField(blank=True, db_index=True, default="", max_length=128)),
                ("utm_medium", models.CharField(blank=True, db_index=True, default="", max_length=128)),
                ("utm_campaign", models.CharField(blank=True, db_index=True, default="", max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Railway traffic log",
                "verbose_name_plural": "Railway traffic logs",
                "ordering": ["-timestamp"],
                "indexes": [
                    models.Index(fields=["timestamp", "http_status"], name="icfes_dashb_timesta_67563d_idx"),
                    models.Index(fields=["timestamp", "bot_category"], name="icfes_dashb_timesta_8b7d03_idx"),
                    models.Index(fields=["timestamp", "school_slug"], name="icfes_dashb_timesta_3886c3_idx"),
                ],
            },
        ),
    ]
