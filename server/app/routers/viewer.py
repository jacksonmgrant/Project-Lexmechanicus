from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
import aioboto3
import os
from ..auth import get_current_user
from ..db import SessionLocal
from ..models import File


router = APIRouter(prefix="/viewer", tags=["viewer"])


S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_BUCKET = os.getenv("S3_BUCKET")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_USE_SSL = bool(int(os.getenv("S3_USE_SSL", "0")))


@router.get("/{file_id}")
async def range_proxy(file_id: int, request: Request, user=Depends(get_current_user)):
    # Authorize access: owner or public file
    async with SessionLocal() as db:
        f = await db.get(File, file_id)
        if not f:
            raise HTTPException(404)
        # TODO: verify ownership or public visibility via joins
    range_hdr = request.headers.get("range") or request.headers.get("Range")
    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        region_name=S3_REGION,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        use_ssl=S3_USE_SSL,
    ) as s3:
        params = {"Bucket": S3_BUCKET, "Key": f.s3_key}
        if range_hdr:
            params["Range"] = range_hdr
        try:
            obj = await s3.get_object(**params)
        except Exception:
            raise HTTPException(404)
        body = await obj["Body"].read()
        status = 206 if range_hdr else 200
        headers = {
            "Content-Type": f.mime_type,
            "Accept-Ranges": "bytes",
        }
        if range_hdr:
            # Pass through Content-Range if provided by S3
            cr = obj.get("ContentRange") or obj.get("Content-Range")
            if cr:
                headers["Content-Range"] = cr
        return Response(content=body, status_code=status, headers=headers)