import os
from celery import Celery

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nss_blood_system.settings')

app = Celery('nss_blood_system')

# Read config keys from Django settings using CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover task modules in all registered Django apps
app.autodiscover_tasks()
