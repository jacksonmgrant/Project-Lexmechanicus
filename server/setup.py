from setuptools import setup

setup(
    name="lexmechanicus-server",
    version="0.1.0",
    packages=["app"],  # ONLY ship app
    install_requires=[
        "fastapi",
        "uvicorn[standard]",
        "SQLAlchemy[asyncio]",
        "asyncpg",
        "pgvector",
        "redis",
        "aioboto3",
        "python-multipart",
        "pydantic",
        "orjson",
        "sse-starlette",
        "httpx",
        "bcrypt",
        "pyjwt",
        "alembic",
        "pypdf",
        "markdown-it-py",
    ],
)
