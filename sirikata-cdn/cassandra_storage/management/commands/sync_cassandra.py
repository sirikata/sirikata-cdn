import pycassa
from pycassa.system_manager import *
from django.core.management.base import NoArgsCommand
import cassandra_storage.settings as settings

class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        sys = SystemManager(server=settings.CASSANDRA_SERVERS[0])
 
        # If there is already a Sirikata-CDN keyspace, we have to ask the user
        # what they want to do with it.
        try:
            sys.get_keyspace_properties(settings.CASSANDRA_KEYSPACE)
            # If there were a keyspace, it would have raised an exception.
            msg = 'Looks like you already have a SirikataCDN keyspace.\nDo you '
            msg += 'want to delete it and recreate it? All current data will '
            msg += 'be deleted! (y/n): '
            resp = raw_input(msg)
            if not resp or resp[0] != 'y':
                print "Ok, then we're done here."
                return
            sys.drop_keyspace(settings.CASSANDRA_KEYSPACE)
        except pycassa.NotFoundException:
            pass
        
        REPLICATION_STRATEGY = getattr(pycassa.system_manager, settings.CASSANDRA_REPLICATION_STRATEGY)
        strategy_options = settings.CASSANDRA_STRATEGY_OPTIONS or {}
        replication_factor = settings.CASSANDRA_REPLICATION_FACTOR
        strategy_options['replication_factor'] = str(replication_factor)
        
        sys.create_keyspace(settings.CASSANDRA_KEYSPACE,
                            replication_strategy=REPLICATION_STRATEGY,
                            strategy_options=strategy_options)
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'Users', comparator_type=UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'Users', 'name', UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'Users', 'email', UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'Users', 'openid_identity', UTF8_TYPE)
        sys.create_index(settings.CASSANDRA_KEYSPACE, 'Users', 'openid_identity', UTF8_TYPE, index_name='openid_identity_index')
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'Users', 'openid_email', UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'Users', 'openid_name', UTF8_TYPE)
        
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'Names', comparator_type=UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'Names', 'type', UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'Names', 'latest', UTF8_TYPE)
        
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'NameTimestampIndex', comparator_type=LONG_TYPE)
        
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'Files', comparator_type=BYTES_TYPE)
        
        #Stores persistent openid associations (used by cassandra_openid.py)
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'OpenIdAssocs', comparator_type=UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdAssocs', 'server_url', UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdAssocs', 'handle', UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdAssocs', 'secret', BYTES_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdAssocs', 'issued', LONG_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdAssocs', 'lifetime', LONG_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdAssocs', 'assoc_type', UTF8_TYPE)
        #Stores openid nonces (used by cassandra_openid.py)
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'OpenIdNonces', comparator_type=UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdNonces', 'server_url', UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdNonces', 'timestamp', LONG_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'OpenIdNonces', 'salt', UTF8_TYPE)

        #Stores web server session information (used by cassandra_sessions_backend.py)
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'Sessions', comparator_type=UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'Sessions', 'serialized', UTF8_TYPE)
        
        #Stores temporary file upload data (used by cassandra_upload_handler.py)
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'TempFiles', comparator_type=UTF8_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'TempFiles', 'size', LONG_TYPE)
        sys.alter_column(settings.CASSANDRA_KEYSPACE, 'TempFiles', 'chunk_list', UTF8_TYPE)

        #Stores results from celery tasks
        sys.create_column_family(settings.CASSANDRA_KEYSPACE, 'CeleryResults', comparator_type=UTF8_TYPE)

        print 'All done!'
