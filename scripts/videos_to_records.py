#!/usr/bin/env python3
"""Create Firestore documents for each object in a GCS bucket."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import firestore
from google.cloud import storage

DEFAULT_GCP_PROJECT = "lunar-2b4b4"
DEFAULT_GCS_BUCKET = "lunar_public"
FIRESTORE_COLLECTION = "videos"
FIRESTORE_BATCH_LIMIT = 500


def iter_object_blobs(bucket: storage.Bucket):
    for blob in bucket.list_blobs():
        if blob.name.endswith("/"):
            continue
        yield blob


def write_media_records(
    db: firestore.Client,
    collection_name: str,
    blobs,
) -> int:
    col = db.collection(collection_name)
    batch = db.batch()
    in_batch = 0
    index = 0
    for blob in blobs:
        index += 1
        doc = col.document()
        batch.set(doc, {"media_url": blob.public_url, "index": index})
        in_batch += 1
        if in_batch >= FIRESTORE_BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            in_batch = 0
    if in_batch:
        batch.commit()
    return index


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    load_dotenv(repo_root / ".env")

    project_id = os.environ.get("GCP_PROJECT", DEFAULT_GCP_PROJECT)

    parser = argparse.ArgumentParser(
        description=(
            "Write Firestore documents {media_url, index} for each bucket object "
            f"(collection {FIRESTORE_COLLECTION!r})."
        ),
    )
    parser.add_argument(
        "bucket",
        nargs="?",
        default=os.environ.get("GCS_BUCKET", DEFAULT_GCS_BUCKET),
        help=(
            f"Bucket name (default: {DEFAULT_GCS_BUCKET} or GCS_BUCKET env)"
        ),
    )
    args = parser.parse_args()
    if not args.bucket:
        parser.error("bucket name is empty")

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    if not raw:
        print("GOOGLE_SERVICE_ACCOUNT_KEY is not set", file=sys.stderr)
        sys.exit(1)

    info = json.loads(raw)
    storage_client = storage.Client.from_service_account_info(
        info, project=project_id
    )
    db = firestore.Client.from_service_account_info(info, project=project_id)
    bucket = storage_client.bucket(args.bucket)

    total = write_media_records(db, FIRESTORE_COLLECTION, iter_object_blobs(bucket))
    print(
        f"Wrote {total} documents to Firestore {FIRESTORE_COLLECTION!r}.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
