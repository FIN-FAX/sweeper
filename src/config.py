import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):

    ENVIRONMENT = os.getenv('ENVIRONMENT')
    
    SRC_FOLDER = os.path.join(os.getenv('APP_FOLDER'), 'src')

    RABBITMQ_USERNAME = os.getenv('RABBITMQ_DEFAULT_USERNAME')
    RABBITMQ_PASSSWORD = os.getenv('RABBITMQ_DEFAULT_PASSSWORD')
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
    RABBITMQ_PORT = os.getenv('RABBITMQ_PORT')

    OUTGOING_QUEUE_EMAILS = os.getenv('QUEUEEMAILS')

    INBOX = '/usr/src/inbox/'
    OUTBOX = '/usr/src/outbox/'
    THUMBNAILS = '/usr/src/thumbnails/'