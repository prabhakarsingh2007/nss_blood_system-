from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("blooddonation", "0003_otp_requestcode_broadcast"),
    ]

    operations = [
        migrations.AddField(
            model_name="donorprofile",
            name="donation_count",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="donorprofile",
            name="rating",
            field=models.FloatField(default=0.0),
        ),
        migrations.CreateModel(
            name="DonationHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("SUCCESS", "Success"), ("FAILED", "Failed")],
                        default="SUCCESS",
                        max_length=10,
                    ),
                ),
                (
                    "donor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="donation_histories",
                        to="blooddonation.donorprofile",
                    ),
                ),
                (
                    "request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="donation_histories",
                        to="blooddonation.bloodrequest",
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
                "constraints": [
                    models.UniqueConstraint(fields=("donor", "request"), name="unique_donation_history_per_request")
                ],
            },
        ),
    ]