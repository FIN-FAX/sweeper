
import datetime
from flask import Flask, jsonify, request, abort, render_template, url_for, redirect
import pika
import os
import json
import time
import requests
import archive
import boto3
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
app.config.from_object("config.Config")

TIMEZONE = "America/Chicago"

def deletefiles(directory):
    threshold = datetime.datetime.now() - datetime.timedelta(days=90)##hours=0, minutes=10
    # print('files in ',directory, [filename for filename in os.listdir(directory)])
    print('delete files older than: ', threshold)
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
            # if '/folder1/' in filepath:
            #     print(filepath, modification_time, threshold)
            if modification_time < threshold:
                # os.remove(filepath)
                if '/inbox/' in filepath and ('/3831410/' in filepath or '/3831411/' in filepath):
                    print('deleting: ',filepath)
                    os.remove(filepath)
                # if '/outbox/' in filepath:
                #     print(filepath)
                if '/outbox/' in filepath and ('_3831410.zip' in filepath or '_3831411.zip' in filepath):
                    print('deleting: ',filepath)
                    os.remove(filepath)
                if '/thumbnails/' in filepath and ('/3831410' in filepath or '/3831411' in filepath):
                    print('deleting: ',filepath)
                    os.remove(filepath)

def deleteoldfiles():
    try:
        inboxsubdirectories = [os.path.join(app.config['INBOX'], d) for d in os.listdir(app.config['INBOX']) if os.path.isdir(os.path.join(app.config['INBOX'], d))]
        for d in inboxsubdirectories:
            deletefiles(d)
        deletefiles(app.config['OUTBOX'])
        # print(os.getenv('THUMBNAILS_FOLDER'), [filename for filename in os.listdir(os.getenv('THUMBNAILS_FOLDER'))])
        deletefiles(app.config['THUMBNAILS']) ## this line is needed only until end of Feb
        thumbnailsubdirectories = [os.path.join(app.config['THUMBNAILS'], d) for d in os.listdir(app.config['THUMBNAILS']) if os.path.isdir(os.path.join(app.config['THUMBNAILS'], d))]
        for d in thumbnailsubdirectories:
            deletefiles(d)
    except Exception as e:
        print(e)
    return
    
# while True:
#     try:
#         print('Going to clean ....', flush = True)
#         archive.cleanoldfiles(app)
#         print('Going to sleep for 1 day ....', flush = True)
#     except Exception as e:
#         print("Error: Something wrong when deleting old faxes ...",e, flush = True)
#     time.sleep(24*60*60)

# scheduler = BlockingScheduler(timezone=TIMEZONE)
scheduler = BackgroundScheduler(timezone=TIMEZONE)
print('adding jobs ...', flush=True)
scheduler.add_job(
        archive.cleanoldfiles,
        trigger="cron",
        hour="1",
        minute="0",
        args=[app]
    )
print('job 1 added ...', flush=True)
scheduler.add_job(
        archive.dump_and_purge_corrected_collection,
        trigger="cron",
        day="2",
        hour="2",
        minute="30",
        args=[app]
    )
print('job 2 added ...', flush=True)
print("Scheduler started. Ctrl+C to exit.", flush=True)
scheduler.start()

try:
    while True:
        print('sleeping ...',flush = True)
        time.sleep(60*60*3)
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()