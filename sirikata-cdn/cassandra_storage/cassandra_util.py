import pycassa
from pycassa.cassandra.ttypes import NotFoundException, InvalidRequestException
from pycassa.cassandra.ttypes import TimedOutException, UnavailableException
import settings

POOL = pycassa.pool.ConnectionPool(settings.CASSANDRA_KEYSPACE,
                                   server_list=settings.CASSANDRA_SERVERS,
                                   timeout=20,
                                   framed_transport=True,
                                   max_retries=5)

READ_CONSISTENCY = getattr(pycassa.ConsistencyLevel, settings.CASSANDRA_READ_CONSISTENCY)
WRITE_CONSISTENCY = getattr(pycassa.ConsistencyLevel, settings.CASSANDRA_WRITE_CONSISTENCY)

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
    return pycassa.ColumnFamily(POOL,
                                name,
                                read_consistency_level=READ_CONSISTENCY,
                                write_consistency_level=WRITE_CONSISTENCY)

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
    
def multiGetRecord(cf, keys, columns=None):
    try:
        return cf.multiget(keys, columns=columns)
    except NotFoundException:
        raise NotFoundError('Record %s not found' % (rowkey,))
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (rowkey))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (rowkey,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (rowkey,))

def getColRange(cf, rowkey, column_start, column_finish, include_timestamp=False,
                column_reversed=False, column_count=100):
    try:
        return cf.get(rowkey, 
                      column_start=column_start, column_finish=column_finish,
                      include_timestamp=include_timestamp, column_count=column_count,
                      column_reversed=column_reversed)
    except NotFoundException:
        raise NotFoundError('Record %s not found' % (rowkey,))
    except InvalidRequestException:
        raise InvalidRequestError('Invalid request for record %s' % (rowkey))
    except TimedOutException:
        raise TimedOutError('Request for record %s timed out' % (rowkey,))
    except UnavailableException:
        raise UnavailableError('Record %s was unavailable' % (rowkey,))

def getRowRange(cf, **kwargs):
    try:
        return cf.get_range(**kwargs)
    except NotFoundException:
        raise NotFoundError('Record not found during row range request')
    except InvalidRequestException:
        raise InvalidRequestError('Invalid row range request')
    except TimedOutException:
        raise TimedOutError('Row range request timed out')
    except UnavailableException:
        raise UnavailableError('Record was unavailable during row range request')

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
    