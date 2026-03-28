from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0011_usersubscription_last_billing_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptionplan",
            name="billing_period",
            field=models.CharField(
                choices=[
                    ("monthly", "Mensual"),
                    ("annual", "Anual"),
                    ("one_time", "Pago único"),
                ],
                default="monthly",
                help_text="Frecuencia de facturación del plan",
                max_length=20,
            ),
        ),
    ]
