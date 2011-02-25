import pycassa
from pycassa.system_manager import *
from django.core.management.base import NoArgsCommand
from cassandra_storage.settings import CASSANDRA_SERVER

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        sys = SystemManager(server=CASSANDRA_SERVER)
 
        # If there is already a Sirikata-CDN keyspace, we have to ask the user
        # what they want to do with it.
        try:
            sys.get_keyspace_properties('SirikataCDN')
            # If there were a keyspace, it would have raised an exception.
            msg = 'Looks like you already have a SirikataCDN keyspace.\nDo you '
            msg += 'want to delete it and recreate it? All current data will '
            msg += 'be deleted! (y/n): '
            resp = raw_input(msg)
            if not resp or resp[0] != 'y':
                print "Ok, then we're done here."
                return
            sys.drop_keyspace('SirikataCDN')
        except pycassa.NotFoundException:
            pass
              
        sys.create_keyspace('SirikataCDN', replication_factor=1)
        sys.create_column_family('SirikataCDN', 'Users', comparator_type=UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'Users', 'name', UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'Users', 'email', UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'Users', 'openid_identity', UTF8_TYPE)
        sys.create_index('SirikataCDN', 'Users', 'openid_identity', UTF8_TYPE, index_name='openid_identity_index')
        sys.alter_column('SirikataCDN', 'Users', 'openid_email', UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'Users', 'openid_name', UTF8_TYPE)
        
        sys.create_column_family('SirikataCDN', 'Names', comparator_type=UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'Names', 'type', UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'Names', 'latest', UTF8_TYPE)
        
        sys.create_column_family('SirikataCDN', 'NameTimestampIndex', comparator_type=UTF8_TYPE)
        
        sys.create_column_family('SirikataCDN', 'Files', comparator_type=BYTES_TYPE)
        
        #Stores persistent openid associations (used by cassandra_openid.py)
        sys.create_column_family('SirikataCDN', 'OpenIdAssocs', comparator_type=UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdAssocs', 'server_url', UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdAssocs', 'handle', UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdAssocs', 'secret', BYTES_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdAssocs', 'issued', LONG_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdAssocs', 'lifetime', LONG_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdAssocs', 'assoc_type', UTF8_TYPE)
        #Stores openid nonces (used by cassandra_openid.py)
        sys.create_column_family('SirikataCDN', 'OpenIdNonces', comparator_type=UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdNonces', 'server_url', UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdNonces', 'timestamp', LONG_TYPE)
        sys.alter_column('SirikataCDN', 'OpenIdNonces', 'salt', UTF8_TYPE)

        #Stores web server session information (used by cassandra_sessions_backend.py)
        sys.create_column_family('SirikataCDN', 'Sessions', comparator_type=UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'Sessions', 'serialized', UTF8_TYPE)
        
        #Stores temporary file upload data (used by cassandra_upload_handler.py)
        sys.create_column_family('SirikataCDN', 'TempFiles', comparator_type=UTF8_TYPE)
        sys.alter_column('SirikataCDN', 'TempFiles', 'size', LONG_TYPE)
        sys.alter_column('SirikataCDN', 'TempFiles', 'chunk_list', UTF8_TYPE)

        #Stores results from celery tasks
        sys.create_column_family('SirikataCDN', 'CeleryResults', comparator_type=UTF8_TYPE)

        print 'All done!'
