# -*- coding: utf-8 -*-
import datetime
import os
import sys
from subprocess import check_output

GOOGLE_OAUTH2_CLIENT_ID = 'unused.setting.com'
GOOGLE_OAUTH2_CLIENT_SECRET = 'UnusedParameter'

try:
    git_hash_command = ['git', 'rev-parse', '--short', 'HEAD']
    git_branch_command = ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
    SANDBAR_VERSION = check_output(git_hash_command) or 'version hash missing'
    CURRENT_BRANCH = check_output(git_branch_command) or 'branch name missing'
except:
    SANDBAR_VERSION = ''
    CURRENT_BRANCH = ''

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EMAIL_TIMEOUT = 10
PING_TIMEOUT = 10

STAGE = 'production'

STAGE_OVERWRITE = os.environ.get('STAGE')
if STAGE_OVERWRITE:
    STAGE = STAGE_OVERWRITE

# SECURITY WARNING: keep the secret key used in production secret!
#################################################
############       UPDATE ME       ##############
#################################################
SECRET_KEY = '{{ SECRET_KEY }}'
#################################################
#################################################
#################################################

import djcelery
djcelery.setup_loader()

BROKER_URL = 'amqp://{{rabbitmq_application_user}}:{{rabbitmq_application_password}}@localhost:5672//'
BROKER_VHOST = '{{ rabbitmq_application_vhost }}'
CELERY_IMPORTS = ('page_parser.tasks', )
CELERY_RESULT_BACKEND = 'amqp://{{rabbitmq_application_user}}:{{rabbitmq_application_password}}@localhost:5672//'
CELERYBEAT_SCHEDULER = "djcelery.schedulers.DatabaseScheduler"
CELERY_ACCEPT_CONTENT = ['pickle']

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'page_parser',
    'client',
    'api',
    'djcelery',
    'bootstrap3',
    'ckeditor',
    'ckeditor_uploader',
    'ShoalScrape',
    'rest_framework',
    'rest_framework_swagger',
    'dynamic_rest',
    'corsheaders',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'client.helpers.ShowLandingPage',
)

ROOT_URLCONF = 'sandbar.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'client.context_processors.accessed_path',
            ],
        },
    },
]
SAVED_HTML = os.path.join(BASE_DIR, "templates", "sites")

WSGI_APPLICATION = 'sandbar.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases
#################################################
############       UPDATE ME       ##############
#################################################
DATABASES = {
    'production': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': '{{ database.name }}',
        'USER': '{{ database.user }}',
        'PASSWORD': '{{ database.password }}',
    }
}
#################################################
#################################################
#################################################

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

ACCOUNT_ACTIVATION_DAYS = 7
REGISTRATION_OPEN = False
LOGIN_REDIRECT_URL = '/clients/list/'
LOGOUT_REDIRECT_URL = '/'

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

#################################################
############       UPDATE ME       ##############
#################################################
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
DEBUG = False
ALLOWED_HOSTS = ('*',)
HOST = '{{ hostname }}.{{ domainname }}'
DATABASES['default'] = DATABASES['production']
#################################################
#################################################
#################################################

CORS_ORIGIN_ALLOW_ALL = True
CORS_URLS_REGEX = r'^/api/.*$'

STATIC_URL = '/static/'
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, "static"),
)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
            'formatter': 'simple',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(asctime)s %(message)s'
        },
    },
}

MEDIA_URL = '/assets/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'assets')

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
    ),
    'PAGE_SIZE': 25,
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
}

DYNAMIC_REST = {
    # ENABLE_LINKS: enable/disable relationship links
    'ENABLE_LINKS': False,
    'PAGE_SIZE': 25,
}

JWT_AUTH = {
    'JWT_ALLOW_REFRESH': True,
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(hours=8),
    'JWT_RESPONSE_PAYLOAD_HANDLER': 'api.utils.jwt_response_payload_handler',
    'JWT_EXPIRATION_DELTA': datetime.timedelta(hours=6),
}

# SSL-related settings
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = False

# ShoalScrape
SHOALSCRAPE_RESULTS_PATH = os.path.join(MEDIA_ROOT, 'shoalscrape')
#################################################
############       UPDATE ME       ##############
######       Integrate with Ansible       #######
#################################################
PHANTOMJS_PATH = '/opt/sandbar/node_modules/phantomjs-prebuilt/lib/phantom/bin/phantomjs'
#################################################
#################################################
#################################################

# Ckeditor
CKEDITOR_JQUERY_URL = '/static/js/jquery-2.1.1.min.js'
CKEDITOR_UPLOAD_PATH = "images/"
CKEDITOR_RESTRICT_BY_USER = False
CKEDITOR_BROWSE_SHOW_DIRS = True

# Settings for running the tests:
if 'test' in sys.argv:
    HOST = 'testserver'
    INSTALLED_APPS += ('django_nose',)
    INSTALLED_APPS += ('sslserver',)
    TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
    NOSE_ARGS = [
        # '--with-coverage',  # NYI, coverage is giving very inaccurate results
        # '--cover-package=client',
        '--nologcapture',
    ]

    # Running Django's tests attempts to create a test database for every database
    # configuration in the DATABASES dictionary, but only one database is needed.
    #################################################
    ############       UPDATE ME       ##############
    #################################################
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'sandbar_test',
            'USER': 'sandbar_test',
            'PASSWORD': 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
            'TEST': {
                'ENGINE': 'django.db.backends.postgresql_psycopg2',
                'NAME': 'sandbar_test',
                'USER': 'sandbar_test',
                'PASSWORD': 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
            },
        },
    }
    #################################################
    #################################################
    #################################################
