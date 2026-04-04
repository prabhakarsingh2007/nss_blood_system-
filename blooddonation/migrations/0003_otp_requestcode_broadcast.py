from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils.crypto import get_random_string


def populate_request_codes(apps, schema_editor):
    BloodRequest = apps.get_model("blooddonation", "BloodRequest")
    for item in BloodRequest.objects.all():
        if item.request_code:
            continue
        code = f"REQ{get_random_string(9, allowed_chars='0123456789')}"
        while BloodRequest.objects.filter(request_code=code).exists():
            code = f"REQ{get_random_string(9, allowed_chars='0123456789')}"
        item.request_code = code
        item.save(update_fields=["request_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("blooddonation", "0002_donor_verification_and_fulfillment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="bloodrequest",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bloodrequest",
            name="assigned_donor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_requests",
                to="blooddonation.donorprofile",
            ),
        ),
        migrations.AddField(
            model_name="bloodrequest",
            name="is_emergency",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="bloodrequest",
            name="otp_code",
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name="bloodrequest",
            name="otp_created_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bloodrequest",
            name="otp_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="bloodrequest",
            name="request_code",
            field=models.CharField(blank=True, max_length=12, null=True),
        ),
        migrations.RunPython(populate_request_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="bloodrequest",
            name="request_code",
            field=models.CharField(blank=True, max_length=12, unique=True),
        ),
        migrations.AddField(
            model_name="donorprofile",
            name="otp_code",
            field=models.CharField(blank=True, max_length=6),
        ),
        migrations.AddField(
            model_name="donorprofile",
            name="otp_created_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="donorprofile",
            name="otp_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="BroadcastMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.CharField(max_length=240)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]