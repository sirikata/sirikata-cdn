from django.core.files.uploadhandler import *
from django.core.files.uploadedfile import *
import cassandra_util as cass
import uuid

class CassandraUploadedFile(UploadedFile):
    """
    A file uploaded into cassandra
    """
    def __init__(self, row_key, chunk_list, size, name=None, content_type=None, charset=None):
        super(CassandraUploadedFile, self).__init__(file=None, name=name, content_type=content_type, size=size, charset=charset)
        self.row_key = row_key
        self.chunk_list = chunk_list

class CassandraFileUploadHandler(FileUploadHandler):
    """
    File upload handler to stream uploads into cassandra.
    """
    def new_file(self, *args, **kwargs):
        super(CassandraFileUploadHandler, self).new_file(*args, **kwargs)
        
        # set chunk size to 256KB. default is 64KB
        self.chunk_size = 256 * 2 ** 10
        
        # generate a random uuid to use for cassandra row key
        self.uuid = uuid.uuid4().hex
        
        self.chunk_list = []
        self._cf = cass.getColumnFamily("TempFiles")
        try:
            cass.insertRecord(self._cf, self.uuid, {})
        except cass.DatabaseError:
            raise UploadFileException("Error inserting temporary file record into cassandra")

    def receive_data_chunk(self, raw_data, start):
        """
        Add the data to the cassandra row
        """
        self.chunk_list.append(start)
        try:
            cass.insertRecord(self._cf, self.uuid, {str(start):raw_data})
        except cass.DatabaseError:
            raise StopUpload("Error inserting chunk at offset %d into cassandra" % start)
        
        # Returning none stops any future handlers from storing the data
        return None

    def file_complete(self, file_size):
        """
        Return a file object if we're activated.
        """
        try:
            columns = {'username':self.request.session.get('username', ''),
                       'size':file_size,
                       'chunk_list':','.join(str(c) for c in self.chunk_list)}
            cass.insertRecord(self._cf, self.uuid, columns)
        except cass.DatabaseError:
            raise UploadFileException("Error inserting final columns into cassandra")
        
        return CassandraUploadedFile(row_key = self.uuid,
                                     chunk_list = self.chunk_list,
                                     size = file_size,
                                     name = self.file_name,
                                     content_type = self.content_type,
                                     charset = self.charset)
