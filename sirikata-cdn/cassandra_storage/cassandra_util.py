import pycassa

POOL = pycassa.connect('SirikataCDN')

class DatabaseError(Exception):
    """
    The base error that functions in this module will raise when things go
    wrong.
    """
    pass

class NotFound(DatabaseError):
    pass

class InvalidDictionary(DatabaseError):
    pass

def getColumnFamily(name):
    return pycassa.ColumnFamily(POOL, name)

def getRecord(cf, id):
    try:
        return cf.get(id)
    except NotFoundException:
        raise NotFound('Record %s not found' % (id,))
