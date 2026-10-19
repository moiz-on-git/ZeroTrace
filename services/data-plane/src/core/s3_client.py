"""
Boto3 S3 client singleton with helpers for the erasure and audit engines.
"""
from __future__ import annotations

import hashlib
import io
from typing import Generator

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger("s3")


def get_s3_client():
    cfg = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=cfg.s3_endpoint,
        aws_access_key_id=cfg.s3_access_key,
        aws_secret_access_key=cfg.s3_secret_key,
        region_name=cfg.s3_region,
        config=Config(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=10,
            read_timeout=60,
        ),
    )


def bucket_is_healthy(s3=None) -> bool:
    cfg = get_settings()
    if s3 is None:
        s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=cfg.s3_bucket)
        return True
    except ClientError:
        return False


def ensure_bucket_exists(versioning: bool = True) -> None:
    """Create the demo bucket if it does not exist, enabling versioning."""
    cfg = get_settings()
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=cfg.s3_bucket)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("404", "NoSuchBucket"):
            kwargs: dict = {"Bucket": cfg.s3_bucket}
            if cfg.s3_region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": cfg.s3_region
                }
            s3.create_bucket(**kwargs)
            logger.info("s3.bucket_created", bucket=cfg.s3_bucket)
        else:
            raise

    if versioning:
        s3.put_bucket_versioning(
            Bucket=cfg.s3_bucket,
            VersioningConfiguration={"Status": "Enabled"},
        )
        logger.info("s3.versioning_enabled", bucket=cfg.s3_bucket)


def iter_all_objects(prefix: str = "") -> Generator[dict, None, None]:
    """Yield every current-version object in the bucket."""
    cfg = get_settings()
    s3 = get_s3_client()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=cfg.s3_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj


def iter_all_versions(prefix: str = "") -> Generator[dict, None, None]:
    """Yield every version (including non-current) of objects."""
    cfg = get_settings()
    s3 = get_s3_client()
    paginator = s3.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=cfg.s3_bucket, Prefix=prefix):
        for v in page.get("Versions", []):
            yield {"kind": "version", **v}
        for dm in page.get("DeleteMarkers", []):
            yield {"kind": "delete_marker", **dm}


def get_object_bytes(key: str, version_id: str | None = None) -> bytes:
    cfg = get_settings()
    s3 = get_s3_client()
    kwargs: dict = {"Bucket": cfg.s3_bucket, "Key": key}
    if version_id:
        kwargs["VersionId"] = version_id
    resp = s3.get_object(**kwargs)
    return resp["Body"].read()


def delete_object_version(key: str, version_id: str) -> None:
    cfg = get_settings()
    s3 = get_s3_client()
    s3.delete_object(Bucket=cfg.s3_bucket, Key=key, VersionId=version_id)


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    cfg = get_settings()
    s3 = get_s3_client()
    s3.put_object(Bucket=cfg.s3_bucket, Key=key, Body=data, ContentType=content_type)


def sha256_of_object(key: str, version_id: str | None = None) -> str:
    data = get_object_bytes(key, version_id)
    return hashlib.sha256(data).hexdigest()
