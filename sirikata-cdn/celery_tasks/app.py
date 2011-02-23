from . import celeryconfig
from celery import Celery
celery_app = Celery()
celery_app.config_from_object(celeryconfig)
