import pycassa
from pycassa.cassandra.ttypes import NotFoundException, InvalidRequestException
from pycassa.cassandra.ttypes import TimedOutException, UnavailableException

POOL = pycassa.connect('SirikataCDN')

class DatabaseError(Exception):
    """
    The base error that functions in this module will raise when things go
    wrong.
    """
    pass

class NotFoundError(DatabaseError):
    pass

class TimedOutError(DatabaseError):
    pass

class UnavailableError(DatabaseError):
    pass

class InvalidRequestError(DatabaseError):
    pass

def getColumnFamily(name):
    return pycassa.ColumnFamily(POOL, name)

def getRecord(cf, rowkey):
    try:
        return cf.get(rowkey)
    except NotFoundException:
        raise NotFoundError('Record %s not found' % (rowkey,))
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (rowkey))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (rowkey,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (rowkey,))

def insertRecord(cf, rowkey, columns):
    try:
        cf.insert(rowkey, columns)
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (rowkey,))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (rowkey,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (rowkey,))

def removeRecord(cf, rowkey):
    try:
        cf.remove(rowkey)
    except NotFoundException:
        raise NotFoundError('Record %s not found' % (rowkey,))
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (id,))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (id,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (id,))
