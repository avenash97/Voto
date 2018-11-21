"""Production config for votr on Heroku."""

import os

DEBUG = False
SECRET_KEY = 'production key'  # keep secret
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
CELERY_BROKER = os.getenv('REDIS_URL')
CELERY_RESULT_BACKEND = 'redis://'
SQLALCHEMY_TRACK_MODIFICATIONS = False
