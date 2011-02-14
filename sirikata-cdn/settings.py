import os

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

DEBUG = True
TEMPLATE_DEBUG = DEBUG

TIME_ZONE = 'America/New_York'
LANGUAGE_CODE = 'en-us'
SITE_ID = 1
USE_I18N = True
USE_L10N = True

MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'media')
MEDIA_URL = '/media/'

# ======= WARNING ============
# Dummy Key. Do not use in production!
# ============================
SECRET_KEY = 'u$az#fnxh2rk=+-lwvjfbkmfxzwq5b8xwrn%y#$-vc9ibb$oxo'

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
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
    'content'
)

#Unused
ADMINS = ()
MANAGERS = ADMINS
DATABASES = {}
ADMIN_MEDIA_PREFIX = '/media/admin/'
