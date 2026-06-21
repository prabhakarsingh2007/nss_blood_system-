from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("blooddonation", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="donorprofile",
            name="verification_status",
            field=models.CharField(
                choices=[("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")],
                default="PENDING",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="bloodrequest",
            name="fulfilled_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fulfilled_requests",
                to="blooddonation.donorprofile",
            ),
        ),
    ]