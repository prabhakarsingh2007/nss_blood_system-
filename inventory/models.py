from django.db import models

class BloodStock(models.Model):
    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
    ]
    
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, unique=True, db_index=True)
    units = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Blood Stocks"
        db_table = "blooddonation_bloodstock"

    def __str__(self):
        return f"{self.blood_group}: {self.units} Units"
        
    @property
    def stock_status(self) -> str:
        if self.units == 0:
            return "OUT OF STOCK"
        elif self.units < 5:
            return "CRITICAL LOW"
        elif self.units < 15:
            return "LOW"
        else:
            return "NORMAL"
