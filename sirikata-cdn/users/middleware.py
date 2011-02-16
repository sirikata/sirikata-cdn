from cassandra_storage.cassandra_util import *

USERS = getColumnFamily('Users')

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

def logout_user(request):
    invalidate_user_cache(request)
    if 'username' in request.session:
        del request.session['username']

def invalidate_user_cache(request):
    if hasattr(request, '_cached_user'):
        delattr(request, '_cached_user')

def get_user(request):
    if 'username' in request.session:
        try:
            cass_user = getRecord(USERS, str(request.session['username']), columns=['name', 'email'])
            user = {}
            user['username'] = request.session['username']
            user['name'] = cass_user['name']
            user['email'] = cass_user['email']
            user['is_authenticated'] = True
            return user
        except DatabaseError:
            pass
    return {'password': None, 'is_authenticated': False}

class LazyUser(object):
    def __get__(self, request, obj_type=None):
        if not hasattr(request, '_cached_user'):
            request._cached_user = get_user(request)
        return request._cached_user

class UserMiddleware(object):
    def process_request(self, request):
        request.__class__.user = LazyUser()
