import os
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
DEBUG_PROPAGATE_EXCEPTIONS = True
# ========= THESE ARE ITEMS YOU MIGHT WANT TO CHANGE ============

#Turn these off in production
DEBUG = True
TEMPLATE_DEBUG = True

#Set to your time zone and language
TIME_ZONE = 'America/New_York'
LANGUAGE_CODE = 'en-us'

#Where media files are located
MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media')
MEDIA_URL = '/media/'

# ======= WARNING ============
# Dummy Key. Do not use in production!
# ============================
SECRET_KEY = 'u$az#fnxh2rk=+-lwvjfbkmfxzwq5b8xwrn%y#$-vc9ibb$oxo'

#OpenID urls can be a function of the realm, so once you set this, don't change it!
OPENID_REALM = 'http://localhost:8000/'

# ===============================================================













# ====== PROBABLY DON'T NEED TO CHANGE ANYTHING BELOW ===========

SITE_ID = 1
USE_I18N = True
USE_L10N = True
SESSION_ENGINE = 'cassandra_storage.cassandra_sessions_backend'
FILE_UPLOAD_HANDLERS = ('cassandra_storage.cassandra_upload_handler.CassandraFileUploadHandler',)
os.environ.setdefault("CELERY_CONFIG_MODULE", "celery_tasks.celeryconfig")

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages'
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'users.middleware.UserMiddleware'
)

ROOT_URLCONF = 'sirikata-cdn.urls'

TEMPLATE_DIRS = (
    os.path.join(PROJECT_ROOT, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.sessions',
    'cassandra_storage',
    'users',
    'content',
    'custom_template_tags'
)

#Unused
ADMINS = ()
MANAGERS = ADMINS
DATABASES = {}
ADMIN_MEDIA_PREFIX = '/media/admin/'
