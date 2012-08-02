import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_USER = "jeff"
BROKER_PASSWORD = "12345678"
BROKER_VHOST = "jeffhost"

CELERY_RESULT_BACKEND = "cassandra"
CASSANDRA_SERVERS = ("localhost:9160",)
CASSANDRA_KEYSPACE = "SirikataCDN"
CASSANDRA_COLUMN_FAMILY = "CeleryResults"
CASSANDRA_READ_CONSISTENCY = "ONE"
CASSANDRA_WRITE_CONSISTENCY = "ANY"
CASSANDRA_OPTIONS = {'pool_size': 1}

CELERY_IMPORTS = (
    "celery_tasks.import_upload",
    "celery_tasks.generate_screenshot",
    "celery_tasks.generate_optimized",
    "celery_tasks.generate_metadata",
    "celery_tasks.generate_progressive",
    "celery_tasks.generate_panda3d",
    "celery_tasks.generate_progressive_errors",
    "celery_tasks.search",
)

CELERY_ROUTES = {
    "celery_tasks.import_upload": {"queue": "realtime"},
    "celery_tasks.generate_screenshot": {"queue": "background_fast"},
    "celery_tasks.generate_optimized": {"queue": "background_fast"},
    "celery_tasks.generate_metadata": {"queue": "background_fast"},
    "celery_tasks.generate_progressive": {"queue": "background_slow"},
    "celery_tasks.generate_panda3d": {"queue": "background_slow"},
    "celery_tasks.generate_progressive_errors": {"queue": "background_slow"},
}
