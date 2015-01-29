# -*- coding: utf-8 -*-
# Django settings for examplesite project.

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
    ('diety', 'kdunn926@gmail.com'), 
)

OUR_APP_NAME = "reHash"

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'forum.db',                      # Or path to database file if using sqlite3.
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

# Local time zone for this installation. All choices can be found here:
# http://www.postgresql.org/docs/8.1/static/datetime-keywords.html#DATETIME-TIMEZONE-SET-TABLE
TIME_ZONE = 'US/Mountain'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
# http://blogs.law.harvard.edu/tech/stories/storyReader$15
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# Enable our userprofile extension
AUTH_PROFILE_MODULE = 'snapboard.UserProfile'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

LANGUAGES = (
    ('en', 'English'),
    ('fr', 'Français'),
)

#LANGUAGE_CODE = 'fr'

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT.
# Example: "http://media.lawrence.com"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/admin/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = '1gzez%G"e42%r(25%%n&@jjvp0g_&#)idxt$)$2%0@%+$at7#@'

STATIC_URL="/static/"

STATICFILES_DIRS = (
    '/Users/kyledunn/snapboard/examplesite/snapboard/lib/',
)

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader', #load_template_source',
    'django.template.loaders.app_directories.Loader', #load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.request",
    "snapboard.views.snapboard_default_context",
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.admindocs.middleware.XViewMiddleware',

    # django-pagination is used by the default templates
    'pagination.middleware.PaginationMiddleware',

    # SNAPBoard middleware
    'snapboard.middleware.threadlocals.ThreadLocals',

    # These are optional
    'snapboard.middleware.ban.IPBanMiddleware',
    'snapboard.middleware.ban.UserBanMiddleware',
)

ROOT_URLCONF = 'snapboard.urls'

TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

use_mailer = True 
use_notification = False
try:
    import notification
except ImportError:
    print 'django-notification not found: email notifications to users will not be available'
else:
    use_notification = True
    try:
        import mailer
    except ImportError:
        pass
    else:
        use_mailer = True

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'ratings',
    'snapboard',
    'pagination',
)

if use_notification:
    INSTALLED_APPS = INSTALLED_APPS + ('notification',)
if use_mailer:
    INSTALLED_APPS = INSTALLED_APPS + ('mailer',)

LOGIN_REDIRECT_URL = '/snapboard/'

# SNAPBoard specific OPTIONAL settings:

# Defaults to MEDIA_URL + 'snapboard/'
SNAP_MEDIA_PREFIX = '/media'

# Set to False to use the default login_required decorator
USE_SNAPBOARD_SIGNIN = True

# Set to False if your templates include the Snapboard login form
USE_SNAPBOARD_LOGIN_FORM = True 

# Select your filter, the default is Markdown
# Possible values: 'bbcode', 'markdown', 'textile'
SNAP_POST_FILTER = 'bbcode'

# Set MEDIA_ROOT so the project works out of the box
import os
MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'snapboard/media')

try:
    from settings_local import *
except ImportError:
    pass
