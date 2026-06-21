from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("blooddonation", "0005_blood_camp_module"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="donationhistory",
            name="certificate_id",
            field=models.CharField(blank=True, max_length=20, unique=True),
        ),
        migrations.AddField(
            model_name="donationhistory",
            name="nss_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="donationhistory",
            name="verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="donationhistory",
            name="verified_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="nss_verified_donations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
