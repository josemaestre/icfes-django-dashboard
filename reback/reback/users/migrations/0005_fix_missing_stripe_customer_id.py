from django.db import migrations


def add_stripe_customer_id_if_missing(apps, schema_editor):
    table_name = "users_user"
    column_name = "stripe_customer_id"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        if connection.vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                [table_name, column_name],
            )
            exists = cursor.fetchone() is not None
            if not exists:
                cursor.execute(
                    f'ALTER TABLE "{table_name}" '
                    f'ADD COLUMN "{column_name}" varchar(255) NOT NULL DEFAULT \'\''
                )
            return

        if connection.vendor == "sqlite":
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            exists = any(row[1] == column_name for row in cursor.fetchall())
            if not exists:
                cursor.execute(
                    f'ALTER TABLE "{table_name}" '
                    f'ADD COLUMN "{column_name}" varchar(255) NOT NULL DEFAULT ""'
                )
            return

        # Fallback for other vendors
        try:
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                [table_name, column_name],
            )
            exists = cursor.fetchone() is not None
        except Exception:
            exists = False

        if not exists:
            cursor.execute(
                f'ALTER TABLE "{table_name}" '
                f'ADD COLUMN "{column_name}" varchar(255) NOT NULL DEFAULT \'\''
            )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_usersubscription_wompi_payment_method_id_and_more"),
    ]

    operations = [
        migrations.RunPython(add_stripe_customer_id_if_missing, migrations.RunPython.noop),
    ]

