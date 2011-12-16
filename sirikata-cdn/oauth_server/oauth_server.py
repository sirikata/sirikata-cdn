import urllib
import oauth2
import sys

from users.middleware import get_api_consumer, get_user_by_username

class CassandraDatastore(object):

    def __init__(self):
        pass

    def lookup_consumer(self, key):
        consumer_info = get_api_consumer(key)
        if consumer_info is None:
            return None
        
        return oauth2.Consumer(consumer_info['consumer_key'], consumer_info['consumer_secret'])

    def lookup_token(self, token_type, token, username):
        if token_type != 'access':
            raise NotImplementedError
        
        user = get_user_by_username(username)
        if user is None:
            print >> sys.stderr, "OAuth token lookup failed for username '%s'" % username
            return None
        
        token = oauth2.Token(user['access_token'], user['access_secret'])
        return token

    def lookup_nonce(self, consumer, token, nonce):
        return None

    def fetch_request_token(self, consumer, callback):
        return None

    def fetch_access_token(self, consumer, token, verifier):
        return None

    def authorize_request_token(self, token, user):
        return None

class OAuthServer(oauth2.Server):
    def __init__(self, signature_methods=None, data_store=None):
        self.data_store = data_store
        super(OAuthServer, self).__init__(signature_methods)

    def fetch_request_token(self, oauth_request):
        raise NotImplementedError

    def fetch_access_token(self, oauth_request):
        raise NotImplementedError

    def authorize_token(self, token, user):
        raise NotImplementedError

    def get_callback(self, oauth_request):
        raise NotImplementedError

    def _get_consumer(self, oauth_request):
        consumer_key = oauth_request.get_parameter('oauth_consumer_key')
        consumer = self.data_store.lookup_consumer(consumer_key)
        if not consumer:
            raise oauth2.Error('Invalid consumer.')
        return consumer

    def _get_token(self, oauth_request, token_type='access', username=None):
        token_field = oauth_request.get_parameter('oauth_token')
        username_field = oauth_request.get_parameter('username')
        token = self.data_store.lookup_token(token_type, token_field, username_field)
        if not token:
            raise oauth2.Error('Invalid %s token: %s' % (token_type, token_field))
        return token

def get_server():
    oauth_server = OAuthServer(data_store=CassandraDatastore())
    oauth_server.add_signature_method(oauth2.SignatureMethod_HMAC_SHA1())
    return oauth_server

def request_from_django(request):
    auth_header =  {}
    if request.META.has_key('HTTP_AUTHORIZATION'):
        auth_header['Authorization'] = request.META['HTTP_AUTHORIZATION']
    parameters = dict(request.REQUEST.items())
    oauth_request = oauth2.Request.from_request(request.method, 
                                               request.build_absolute_uri(), 
                                               headers=auth_header,
                                               parameters=parameters)
    return oauth_request

def verify_access_request(oauth_request):
    try:
        oauth_server = get_server()
        consumer = oauth_server._get_consumer(oauth_request)
        token = oauth_server._get_token(oauth_request, token_type='access')
        params = oauth_server.verify_request(oauth_request, consumer, token)
        return True
    except oauth2.Error, ex:
        print >> sys.stderr, 'OAuth error: ', ex
        return False
