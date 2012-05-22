from cassandra_storage.cassandra_util import *
import json
import datetime
import operator
from django.conf import settings
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from functools import wraps

SUPERUSERS = getattr(settings, 'SUPERUSERS', [])
USERS = getColumnFamily('Users')
API_CONSUMERS = getColumnFamily('APIConsumers')

def get_pending_uploads(username):
    try:
        pending_range = getColRange(USERS, username, column_start="uploading:.",
                                    column_finish="uploading:~", include_timestamp=True)
    except DatabaseError:
        return []

    records = []

    for colkey, (value, timestamp) in pending_range.iteritems():
        task_id = colkey.split(":")[1]
        values = json.loads(value)
        values['task_id'] = task_id
        values['timestamp'] = datetime.datetime.fromtimestamp(timestamp / 1e6)
        records.append(values)

    records = sorted(records, key=operator.itemgetter("timestamp"), reverse=True)

    return records

def get_uploads(username):
    try:
        upload_range = getColRange(USERS, username, column_start="uploaded:.",
                                    column_finish="uploaded:~", include_timestamp=True)
    except DatabaseError:
        return []

    records = []
    for colkey, (value, timestamp) in upload_range.iteritems():
        values = {}
        values['path'] = colkey.split(":")[1]
        values['timestamp'] = datetime.datetime.fromtimestamp(timestamp / 1e6)
        records.append(values)

    records = sorted(records, key=operator.itemgetter("timestamp"), reverse=True)

    return records

def get_pending_upload(username, task_id):
    col_key = "uploading:%s" % task_id

    pending = getRecord(USERS, username, columns=[col_key])

    values = json.loads(pending[col_key])
    values['task_id'] = task_id
    return values

def remove_pending_upload(username, task_id):
    col_key = "uploading:%s" % task_id

    removeColumns(USERS, username, columns=[col_key])

def save_upload_task(username, task_id, row_key, filename, subfiles, dae_choice, task_name, ephemeral=False):
    vals = {"main_rowkey":row_key, "filename":filename,"subfiles":subfiles,
            'dae_choice':dae_choice, 'task_name': task_name, 'ephemeral': ephemeral}
    upload_rec = json.dumps(vals)
    task = {"uploading:%s" % task_id : upload_rec}
    insertRecord(USERS, username, columns=task)

def save_file_upload(username, path):
    insertRecord(USERS, username, columns={"uploaded:%s" % path : ""})

def remove_file_upload(username, path):
    removeColumns(USERS, username, columns=["uploaded:%s" % path])

def login_with_openid_identity(request, identity_url):
    try:
        for key, user in getRecordsByIndex(USERS, 'openid_identity', identity_url, count=1, columns=['name', 'email']):
            request.session['username'] = key
            invalidate_user_cache(request)
            return True
        return False
    except NotFoundError:
        return False
    except DatabaseError:
        raise

def associate_openid_login(request, identity_url, openid_email, openid_name, username, email, name):
    #Check if username already exists
    try:
        previously = getRecord(USERS, username, columns=['name'])
        return False
    except NotFoundError:
        pass
    except DatabaseError:
        raise

    columns = {'name':name,
               'email':email,
               'openid_identity':identity_url,
               'openid_name':openid_name,
               'openid_email':openid_email}
    try:
        insertRecord(USERS, username, columns)
    except DatabaseError:
        return False

    request.session['username'] = username
    invalidate_user_cache(request)
    return True

def add_user_metadata(request, username, **kwargs):
    insertRecord(USERS, username, kwargs)
    invalidate_user_cache(request)

def remove_api_consumer(request):
    username = request.user['username']
    consumer_key = request.user['consumer_key']
    
    removeRecord(API_CONSUMERS, consumer_key)
    
    insertRecord(USERS, username, dict(
                 consumer_key = '',
                 consumer_secret = ''))
    
    invalidate_user_cache(request)

def get_api_consumer(consumer_key):
    try:
        consumer_record = getRecord(API_CONSUMERS, consumer_key, columns=['consumer_key', 'consumer_secret', 'username'])
    except DatabaseError:
        return None
    
    if not(all(k in consumer_record for k in ['consumer_key', 'consumer_secret', 'username'])):
        return None
    
    consumer_info = {}
    consumer_info['consumer_key'] = consumer_record['consumer_key']
    consumer_info['consumer_secret'] = consumer_record['consumer_secret']
    consumer_info['username'] = consumer_record['username']
    
    return consumer_info

def add_api_consumer(request, username, consumer_key, consumer_secret):
    insertRecord(API_CONSUMERS, consumer_key, dict(
                 username = username,
                 consumer_key = consumer_key,
                 consumer_secret = consumer_secret))

    insertRecord(USERS, username, dict(
                 consumer_key = consumer_key,
                 consumer_secret = consumer_secret))
    
    invalidate_user_cache(request)

def logout_user(request):
    invalidate_user_cache(request)
    if 'username' in request.session:
        del request.session['username']

def invalidate_user_cache(request):
    if hasattr(request, '_cached_user'):
        delattr(request, '_cached_user')

def get_user_by_username(username):
    try:
        cass_user = getRecord(USERS, str(username), columns=['name',
                                                             'email',
                                                             'access_token',
                                                             'access_secret',
                                                             'consumer_key',
                                                             'consumer_secret'])
        user = {}
        user['username'] = username
        user['is_superuser'] = username in SUPERUSERS
        user['name'] = cass_user['name']
        user['email'] = cass_user['email']
        user['access_token'] = cass_user.get('access_token')
        user['access_secret'] = cass_user.get('access_secret')
        user['consumer_key'] = cass_user.get('consumer_key')
        user['consumer_secret'] = cass_user.get('consumer_secret')
        return user
    except DatabaseError:
        return None

def get_user(request):
    if 'username' in request.session:
        user = get_user_by_username(request.session['username'])
        if user:
            user['is_authenticated'] = True
            return user
    return {'password': None, 'is_authenticated': False}

class LazyUser(object):
    def __get__(self, request, obj_type=None):
        if not hasattr(request, '_cached_user'):
            request._cached_user = get_user(request)
        return request._cached_user

class UserMiddleware(object):
    def process_request(self, request):
        request.__class__.user = LazyUser()

def login_required(f):
    @wraps(f)
    def wrapper(request, *args, **kwargs):
        if not request.user['is_authenticated']:
            return redirect('users.views.login')
        return f(request, *args, **kwargs)
    
    return wrapper

def superuser_required(f):
    @wraps(f)
    def wrapper(request, *args, **kwargs):
        if not request.user['is_authenticated']:
            return redirect('users.views.login')
        if not request.user['is_superuser']:
            return HttpResponseForbidden()
        return f(request, *args, **kwargs)
    
    return wrapper
