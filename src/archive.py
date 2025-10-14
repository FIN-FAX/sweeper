import boto3
from boto3.s3.transfer import S3Transfer, TransferConfig
import os
from datetime import datetime, timezone, timedelta
import time
import requests

# ─── CONFIG ─────────────────────────────────────────────────────────
NAS_BASE_PATH = '/usr/src/archive'
DELETE_PREFIXES = ['outbox/']

BUCKET_NAME = os.getenv('S3BUCKETNAME')

# ────────────────────────────────────────────────────────────────────

def gets3client():
    if os.getenv('ENVIRONMENT') == 'dev':
        print('setting boto3 profile name ... to dev')
        aws_access_key_id=os.getenv('AWSKEYID')
        aws_secret_access_key=os.getenv('AWSACCESSKEY')

        s3_client = boto3.client("s3", 
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name="us-east-1")

    elif os.getenv('ENVIRONMENT') == 'prod':
        s3_client = boto3.client('s3')
    return s3_client

def list_old_objects(bucket, prefix, cutoff):
    """Yield all S3 objects under `prefix` older than cutoff datetime."""
    s3_client = gets3client()
    paginator = s3_client.get_paginator('list_objects_v2')
    old_objects = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        # print('page',page,flush=True)
        for obj in page.get('Contents', []):
            # print(obj['LastModified'],obj['LastModified'] < cutoff, flush=True)
            if obj['LastModified'] < cutoff:
                old_objects.append({
                    'Key': obj['Key'],
                    'LastModified': obj['LastModified'],
                    'Size': obj['Size']
                })

    return old_objects

def move_old_tifs_inbox_s3(app,bucket, nas_base, cutoff):
    s3_client = gets3client()
    for obj in list_old_objects(bucket, 'inbox/', cutoff):
        key = obj['Key']
        # print('key: ',key,flush=True)
        if not key.lower().endswith('.tif'):
            continue
        # Extract faxline (first subfolder under 'inbox/')
        parts = key.split('/')
        # print(parts)
        if len(parts) < 3:
            continue  # skip if not at least inbox/<faxline>/<file>
        _, faxline, filename = parts[0], parts[1], parts[-1]

        # fileId is filename without .tif
        fileId, _ = os.path.splitext(filename)

        # 1) Call your delete endpoint before archiving
        payload = {'fileId': fileId, 'faxline': faxline}
        print(payload, obj['LastModified'], flush=True)
        
        url = f'http://faxdb-finfax-{app.config["ENVIRONMENT"]}:8012/delete'
        try:
            resp = requests.post(url, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"❌ Skipping {key}: delete-endpoint call failed: {e}")
            continue

        # 2) Proceed to download and delete from S3
        year = obj['LastModified'].year
        # Build relative path under inbox (excluding filename)
        rel_dir = os.path.dirname(key[len('inbox/'):])
        local_dir = os.path.join(nas_base, 'inbox', rel_dir, str(year))
        os.makedirs(local_dir, exist_ok=True)

        local_path = os.path.join(local_dir, filename)
        print(f"⬇ Downloading s3://{bucket}/{key} → {local_path}")
        s3_client.download_file(bucket, key, local_path)

        print(f"🗑 Deleting s3://{bucket}/{key}")
        s3_client.delete_object(Bucket=bucket, Key=key)

def delete_old_under_prefixes_s3(bucket, prefixes, cutoff):
    s3_client = gets3client()
    """Delete all objects older than cutoff under each given prefix."""
    for prefix in prefixes:
        for obj in list_old_objects(bucket, prefix, cutoff):
            key = obj['Key']
            print(f"> Deleting s3://{bucket}/{key}, {obj['LastModified']}" )
            s3_client.delete_object(Bucket=bucket, Key=key)

def move_old_under_prefixes_s3(src_bucket, prefixes, cutoff, dst_bucket, dst_prefix=""):
    """
    Move (copy then delete) all objects older than `cutoff` under each given prefix
    from `src_bucket` to `dst_bucket`. If `dst_prefix` is set, it's prepended to
    the destination key (original key is preserved after that prefix).

    cutoff: timezone-aware datetime (e.g., datetime.now(timezone.utc) - timedelta(days=10))
    """
    s3_client = gets3client()

    # Ensure dst_prefix ends with '/' if provided and not already
    if dst_prefix and not dst_prefix.endswith('/'):
        dst_prefix = dst_prefix + '/'

    for prefix in prefixes:
        for obj in list_old_objects(src_bucket, prefix, cutoff):
            key = obj["Key"]
            dst_key = f"{dst_prefix}{key}"

            copy_source = {"Bucket": src_bucket, "Key": key}

            try:
                print(f"> Copying s3://{src_bucket}/{key}  ->  s3://{dst_bucket}/{dst_key}")
                # Use s3_client.copy() and pass the TransferConfig
                s3_client.copy_object(
                    CopySource=copy_source,
                    Bucket=dst_bucket,
                    Key=dst_key
                )
                # If copy succeeds, delete original
                s3_client.delete_object(Bucket=src_bucket, Key=key)
                print(f"✓ Moved (deleted source): s3://{src_bucket}/{key}")
            except ClientError as e:
                # Handle errors during the copy or delete process.
                print(f"Error moving object: {e}")
            except Exception as e:
                # Copy failed; do NOT delete the source
                print(f"✗ Failed to move {key}: {e}")

def cleanoldfiles(app,DAYS_OLD=90):
    print('Going to clean old files  ...', datetime.now(), flush=True)
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=DAYS_OLD)
    move_old_tifs_inbox_s3(app,BUCKET_NAME, NAS_BASE_PATH, cutoff_dt)
    # delete_old_under_prefixes_s3(BUCKET_NAME, DELETE_PREFIXES, cutoff_dt)
    move_old_under_prefixes_s3(
        src_bucket=BUCKET_NAME,
        prefixes=DELETE_PREFIXES,              # add more prefixes if needed
        cutoff=datetime.now(timezone.utc) - timedelta(days=10),
        dst_bucket="idfax-outbox-backup",  # destination bucket
        dst_prefix=""                      # or e.g. "backup" to nest under backup/
    )
    print("Done ...")

def dump_and_purge_corrected_collection(app):
    print('Going to dump and purge corrected collections ...', datetime.now(), flush=True)
    url = f'http://faxdb-finfax-{app.config["ENVIRONMENT"]}:8012/dumppurge_corrected_collections'
    try:
        resp = requests.get(url, timeout=7200)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ dump and purge corrected call failed: {e}")
    