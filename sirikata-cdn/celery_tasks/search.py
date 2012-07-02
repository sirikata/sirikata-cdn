import datetime
from celery.task import task, current
from django.conf import settings
from content.utils import get_model_data_from_path, get_file_metadata
from content.utils import item_to_search_fields, get_content_by_date
from cassandra_storage.cassandra_util import NotFoundError
import pysolr
import traceback

def do_update(full_path):
    SOLR_URL = getattr(settings, 'SOLR_WRITE_URL')
    SOLR_CONNECTION = None if SOLR_URL is None else pysolr.Solr(SOLR_URL)
    
    if SOLR_CONNECTION is None:
        return 0
        
    model_data = get_model_data_from_path(full_path)
    try:
        model_data['metadata'] = get_file_metadata(full_path)
    except NotFoundError:
        SOLR_CONNECTION.delete(id=full_path)
        return
    
    if model_data['metadata'].get('ephemeral', False):
        return 1
    
    model_data['timestamp'] = datetime.datetime.fromtimestamp(model_data['metadata']['timestamp'] / 1e6)
    to_insert = [item_to_search_fields(model_data)]
    SOLR_CONNECTION.add(to_insert)
    return 1

@task(max_retries=None)
def update_single_search_index_item(full_path):
    try:
        return do_update(full_path)
    except Exception, exc:
        print 'Update search index got exception'
        print exc
        traceback.print_exc(exc)
        # exponential retry backoff, in seconds: 1, 2, 4, 16, 32, 64, 128
        current.retry(exc=exc, countdown=min(2 ** current.request.retries, 128))

@task
def update_entire_search_index():
    SOLR_URL = getattr(settings, 'SOLR_WRITE_URL')
    SOLR_CONNECTION = None if SOLR_URL is None else pysolr.Solr(SOLR_URL)
    
    if SOLR_CONNECTION is None:
        return 0
    
    (content_items, older_start, newer_start) = get_content_by_date(start="", limit=2000000)
    
    items_to_insert = []
    for item in content_items:
        items_to_insert.append(item_to_search_fields(item))
    
    SOLR_CONNECTION.delete(q='*:*')
    SOLR_CONNECTION.add(items_to_insert)
    return len(items_to_insert)
