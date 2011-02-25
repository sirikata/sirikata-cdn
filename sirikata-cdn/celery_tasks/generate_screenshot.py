import collada as coll
from celery.task import task
import cassandra_storage.cassandra_util as cass
from StringIO import StringIO
import os.path
import hashlib
import json

import time
import sys

@task
def generate_screenshot():
    pass