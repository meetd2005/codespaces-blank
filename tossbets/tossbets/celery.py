import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tossbets.settings")

app = Celery("tossbets")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
