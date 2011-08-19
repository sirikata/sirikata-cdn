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

CELERY_IMPORTS = (
    "celery_tasks.import_upload",
    "celery_tasks.generate_screenshot",
    "celery_tasks.generate_optimized",
    "celery_tasks.generate_metadata"
)
