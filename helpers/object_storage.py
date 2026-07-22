import asyncio
from pathlib import Path, PurePosixPath
from typing import Protocol


class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...


def _safe_relative_key(key: str) -> Path:
    normalized = PurePosixPath(key)
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise ValueError("Object storage key must be a safe relative path")
    return Path(*normalized.parts)


class LocalObjectStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    async def put(self, key: str, data: bytes, _content_type: str) -> None:
        target = self.root / _safe_relative_key(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_bytes, data)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread((self.root / _safe_relative_key(key)).read_bytes)

    async def delete(self, key: str) -> None:
        target = self.root / _safe_relative_key(key)
        if target.exists():
            await asyncio.to_thread(target.unlink)


class S3ObjectStorage:
    def __init__(self, bucket: str, prefix: str = "", session=None):
        if not bucket:
            raise ValueError("S3 bucket is required")
        if session is None:
            import aioboto3

            session = aioboto3.Session()
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.session = session

    def _key(self, key: str) -> str:
        safe_key = _safe_relative_key(key).as_posix()
        return f"{self.prefix}/{safe_key}" if self.prefix else safe_key

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        async with self.session.client("s3") as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=self._key(key),
                Body=data,
                ContentType=content_type,
            )

    async def get(self, key: str) -> bytes:
        async with self.session.client("s3") as client:
            response = await client.get_object(Bucket=self.bucket, Key=self._key(key))
            async with response["Body"] as body:
                return await body.read()

    async def delete(self, key: str) -> None:
        async with self.session.client("s3") as client:
            await client.delete_object(Bucket=self.bucket, Key=self._key(key))
