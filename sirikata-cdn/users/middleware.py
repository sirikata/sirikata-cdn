from cassandra_storage.cassandra_util import *

USERS = getColumnFamily('Users')

def get_user(request):
    if 'username' in request.session:
        try:
            user = getRecord(USERS, str(request.session['username']))
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
