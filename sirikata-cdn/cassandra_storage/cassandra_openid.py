import cassandra_util as cass
import hashlib
import time
from openid.association import Association
from openid.store import nonce

class CassandraStore(object):
    """Openid Store for Cassandra.
    """
    
    def __init__(self):
        self._cf = cass.getColumnFamily("OpenIdAssocs")
        self._nonce_cf = cass.getColumnFamily("OpenIdNonces")

    def storeAssociation(self, server_url, assoc):
        server_url_hash = hashlib.sha256(server_url).hexdigest()
        handle_hash = hashlib.sha256(assoc.handle).hexdigest()
        rowkey = "%s_%s" % (server_url_hash, handle_hash)
        
        columns = {'server_url': server_url,
                   'handle': assoc.handle,
                   'secret': assoc.secret,
                   'issued': assoc.issued,
                   'lifetime': assoc.lifetime,
                   'assoc_type': assoc.assoc_type}
        
        try:
            cass.insertRecord(self._cf, rowkey, columns)
        except cass.DatabaseError:
            raise

    def getAssociation(self, server_url, handle=None):
        if handle is None:
            return None

        server_url_hash = hashlib.sha256(server_url).hexdigest()
        handle_hash = hashlib.sha256(handle).hexdigest()
        rowkey = "%s_%s" % (server_url_hash, handle_hash)
        
        try:
            assoc_rec = cass.getRecord(self._cf, rowkey)
        except cass.NotFoundError:
            return None
        except cass.DatabaseError:
            raise
        
        server_url = assoc_rec['server_url']
        handle = assoc_rec['handle']
        secret = assoc_rec['secret']
        issued = assoc_rec['issued']
        lifetime = assoc_rec['lifetime']
        assoc_type = assoc_rec['assoc_type']
        
        association = Association(handle, secret, issued, lifetime, assoc_type)
        
        if association.getExpiresIn() == 0:
            return None
        
        return association

    def removeAssociation(self, server_url, handle):
        server_url_hash = hashlib.sha256(server_url).hexdigest()
        handle_hash = hashlib.sha256(handle).hexdigest()
        rowkey = "%s_%s" % (server_url_hash, handle_hash)
        
        try:
            cass.removeRecord(self._cf, rowkey)
            return True
        except cass.NotFoundError:
            return False
        except cass.DatabaseError:
            raise

    def useNonce(self, server_url, timestamp, salt):
        if abs(timestamp - time.time()) > nonce.SKEW:
            return False

        server_url_hash = hashlib.sha256(server_url).hexdigest()
        rowkey = "%s_%s_%s" % (server_url_hash, str(timestamp), str(salt))
        
        #Let's check if this nonce exists
        try:
            assoc_rec = cass.getRecord(self._nonce_cf, rowkey)
        except cass.NotFoundError:
            columns = {'server_url': server_url,
                       'timestamp': timestamp,
                       'salt': salt}
            #Not found so try and insert
            try:
                cass.insertRecord(self._nonce_cf, rowkey, columns)
                #Inserted successfully, nonce is valid
                return True
            except cass.DatabaseError:
                raise
        except cass.DatabaseError:
            raise
        else:
            #Nonce already existed so nonce is invalid
            return False

    def cleanupNonces(self):
        pass

    def cleanupAssociations(self):
        pass
