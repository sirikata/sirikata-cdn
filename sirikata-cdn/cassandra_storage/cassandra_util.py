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

def getRecord(cf, rowkey, columns=None):
    try:
        return cf.get(rowkey, columns=columns)
    except NotFoundException:
        raise NotFoundError('Record %s not found' % (rowkey,))
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (rowkey))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (rowkey,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (rowkey,))

def getColRange(cf, rowkey, column_start, column_finish, include_timestamp=False):
    try:
        return cf.get_range(start=rowkey, finish=rowkey, 
                            column_start=column_start, column_finish=column_finish,
                            include_timestamp=include_timestamp)
    except NotFoundException:
        raise NotFoundError('Record %s not found' % (rowkey,))
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (rowkey))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (rowkey,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (rowkey,))

def getRecordsByIndex(cf, column, value, count=100, columns=None):
    try:
        expr = pycassa.index.create_index_expression(column, value)
        clause = pycassa.index.create_index_clause([expr], count=count)
        for key, user in cf.get_indexed_slices(clause, columns=columns):
            yield key, user
    except NotFoundException:
        raise NotFoundError('Record not found')
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record')
    except TimedOutException:
        raise TimedOutError('Request for record timed out')
    except UnavailableException:
        raise UnavailableError('Record was unavailable')

def insertRecord(cf, rowkey, columns, ttl=None):
    try:
        cf.insert(rowkey, columns, ttl=ttl)
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (rowkey,))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (rowkey,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (rowkey,))

def removeColumns(cf, rowkey, columns):
    try:
        return cf.remove(rowkey, columns=columns)
    except NotFoundException:
        raise NotFoundError('Record %s not found' % (rowkey,))
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (id,))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (id,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (id,))

def removeRecord(cf, rowkey):
    return removeColumns(cf, rowkey, columns=None)
    