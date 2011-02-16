from django.contrib.sessions.backends.base import SessionBase, CreateError
import cassandra_util as cass

class SessionStore(SessionBase):
    """
    A cassandra-based session store.
    """
    def __init__(self, session_key=None):
        self._cf = cass.getColumnFamily("Sessions")
        super(SessionStore, self).__init__(session_key)

    def load(self):
        try:
            session_rec = cass.getRecord(self._cf, self.session_key)
            return self.decode(session_rec['serialized'])
        except cass.NotFoundError:
            self.create()
            return {}
        except cass.DatabaseError:
            raise

    def create(self):
        while True:
            self.session_key = self._get_new_session_key()
            try:
                self.save(must_create=True)
            except CreateError:
                continue
            self.modified = True
            return

    def save(self, must_create=False):
        if must_create and self.exists(self.session_key):
            raise CreateError
        
        session_key = self.session_key
        session_data = self.encode(self._get_session(no_load=must_create))
        expire_age = self.get_expiry_age()
        try:
            cass.insertRecord(self._cf, session_key, {'serialized':session_data}, ttl=expire_age)
        except cass.DatabaseError:
            raise

    def exists(self, session_key):
        try:
            session_rec = cass.getRecord(self._cf, session_key)
            return True
        except cass.NotFoundError:
            return False
        except cass.DatabaseError:
            raise

    def delete(self, session_key=None):
        if session_key is None:
            if self._session_key is None:
                return
            session_key = self._session_key
        try:
            cass.removeRecord(self._cf, session_key)
        except cass.NotFoundError:
            pass
        except cass.DatabaseError:
            raise

