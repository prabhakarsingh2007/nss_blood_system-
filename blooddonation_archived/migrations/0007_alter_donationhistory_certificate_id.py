from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blooddonation", "0006_donationhistory_nss_certificate"),
    ]

    operations = [
        migrations.AlterField(
            model_name="donationhistory",
            name="certificate_id",
            field=models.CharField(blank=True, default=None, max_length=20, null=True, unique=True),
        ),
    ]
