"""
Django settings for waveform annotation project.

Generated by 'django-admin startproject' using Django 1.11.5.

For more information on this file, see
https://docs.djangoproject.com/en/1.11/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.11/ref/settings/
"""
import os

from decouple import config

# Basic settings based on development environment
DEBUG = config('DEBUG', default=False, cast=bool)
SESSION_COOKIE_SECURE = False
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

ALLOWED_HOSTS = ['*']

def custom_show_toolbar(request):
    return True

DEBUG_TOOLBAR_CONFIG = {
    'JQUERY_URL': '',
    # 'SHOW_TOOLBAR_CALLBACK': custom_show_toolbar,
}

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(PROJECT_DIR)
HEAD_DIR = os.path.dirname(BASE_DIR)
LOGIN_URL = 'login'

# For password resets
# Check output in another terminal window here:
#   python -m smtpd -n -c DebuggingServer localhost:1025
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=1025, cast=int)
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
EMAIL_FROM = 'help@waveform-annotation.com'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.11/howto/deployment/checklist/

SECRET_KEY = config('SECRET_KEY')

# Application definition

INSTALLED_APPS = [
    'debug_toolbar',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'django_plotly_dash.apps.DjangoPlotlyDashConfig',
    'django.contrib.sessions',
    'django.contrib.messages',

    'graphene_django',

    'export',
    'waveforms',
    'website'
]

MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'website.middleware.thread_local_middleware'
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(HEAD_DIR,'db','db.sqlite3')
    }
}

ROOT_URLCONF = 'website.urls'

if not DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'timestamp': {
                'format': '{asctime} {levelname} {message}',
                'style': '{',
            },
        },
        'handlers': {
            'file': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filename': os.path.join(HEAD_DIR, 'debug', 'debug.log'),
                'formatter': 'timestamp'
            }
        },
        'loggers': {
            'django': {
                'handlers': ['file'],
                'level': 'DEBUG',
            },
        },
    }

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR,'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

X_FRAME_OPTIONS = 'SAMEORIGIN'

PLOTLY_COMPONENTS = [
    'dash_core_components',
    'dash_html_components',
    'dash_renderer',
    'dpd_components'
]

# Session management

# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Django background tasks max attempts
MAX_ATTEMPTS = 5

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/
#USE_X_FORWARDED_HOST = True
#FORCE_SCRIPT_NAME = '/waveform-annotation'

STATIC_URL = '/static/'
if DEBUG:
    STATIC_ROOT = 'static'
    STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
else:
    STATIC_ROOT = os.path.join(BASE_DIR, 'static')
    STATICFILES_DIRS = [os.path.join(PROJECT_DIR, 'static')]
STATICFILE_FINDERS = [
    'django.contrib.staticfiles.finder.FileSystemFinder',
    'django.contrib.staticfiles.finder.AppDirectoriesFinder',
    'django_plotly_dash.finders.DashAssetFinder',
    'django_plotly_dash.finders.DashComponentFinder',
]

RECORDS_FILE = 'RECORDS_VTVF'
ASSIGNMENT_FILE = 'user_assignments.csv'
ALL_PROJECTS = ['2015_data', '2021_data']

# Projects in blacklist cannot be automatically assigned to users
BLACKLIST = ['2021_data']

# Events to be used in the practice data set
PRACTICE_SET = {
    '2015_data': {'ge1_1m': True, 'ge9_10m': False},
}

# List of permitted HTML tags and attributes for rich text fields.
# The 'default' configuration permits all of the tags below.  Other
# configurations may be added that permit different sets of tags.

# Attributes that can be added to any HTML tag
_generic_attributes = ['lang', 'title']
