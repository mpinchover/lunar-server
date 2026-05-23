#!/usr/bin/env python3
"""Download all objects from lunar-public/videos in GCS."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import storage

DEFAULT_GCP_PROJECT = "callysto-6286f"
DEFAULT_GCS_BUCKET = "lunar-public"
DEFAULT_PREFIX = "videos/"


def get_storage_client(project_id: str) -> storage.Client:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    if raw:
        info = json.loads(raw)
        return storage.Client.from_service_account_info(info, project=project_id)
    return storage.Client(project=project_id)


def iter_video_blobs(bucket: storage.Bucket, prefix: str):
    for blob in bucket.list_blobs(prefix=prefix):
        if blob.name.endswith("/"):
            continue
        yield blob


def local_path_for_blob(blob_name: str, prefix: str, out_dir: Path) -> Path:
    if blob_name.startswith(prefix):
        relative = blob_name[len(prefix) :]
    else:
        relative = Path(blob_name).name
    return out_dir / relative


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    load_dotenv(repo_root / ".env")

    parser = argparse.ArgumentParser(
        description="Download all objects from a GCS bucket prefix.",
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GCP_PROJECT", DEFAULT_GCP_PROJECT),
        help=f"GCP project id (default: {DEFAULT_GCP_PROJECT})",
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("GCS_BUCKET", DEFAULT_GCS_BUCKET),
        help=f"GCS bucket name (default: {DEFAULT_GCS_BUCKET})",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Object prefix inside the bucket (default: {DEFAULT_PREFIX!r})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_dir / "output",
        help="Output directory (default: scripts/output)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip files that already exist locally with the same size",
    )
    args = parser.parse_args()

    prefix = args.prefix
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    out_dir = args.output.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    client = get_storage_client(args.project)
    bucket = client.bucket(args.bucket)

    downloaded = 0
    skipped = 0
    failed = 0

    for blob in iter_video_blobs(bucket, prefix):
        dest = local_path_for_blob(blob.name, prefix, out_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if args.skip_existing and dest.is_file():
            if dest.stat().st_size == blob.size:
                skipped += 1
                continue

        try:
            blob.download_to_filename(str(dest))
            downloaded += 1
            print(dest.name, file=sys.stderr)
        except Exception as exc:
            failed += 1
            print(f"failed {blob.name}: {exc}", file=sys.stderr)

    print(
        f"Done: {downloaded} downloaded, {skipped} skipped, {failed} failed "
        f"-> {out_dir}",
        file=sys.stderr,
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
