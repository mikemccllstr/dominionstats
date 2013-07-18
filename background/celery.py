from __future__ import absolute_import

from celery import Celery

celery = Celery('background.celery',
                backend='redis://cr-master-internal.mccllstr.com:6379/0',
                broker='redis://cr-master-internal.mccllstr.com:6379/0',
                include=['background.tasks'])

#celery = Celery('background.celery',
                #backend='redis://127.0.0.1:6379/0',
                #broker='redis://127.0.0.1:6379/0',
                #include=['background.tasks'])

# Optional configuration, see the application user guide.
celery.conf.update(
    CELERY_TASK_RESULT_EXPIRES=3600,
)

if __name__ == '__main__':
    celery.start()
