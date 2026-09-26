"""Firebase Functions entrypoint for the FastAPI backend.

The application factory remains separate so local development can run with
Uvicorn while Firebase owns the public HTTPS function in production.
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from functions_framework import http
from mangum import Mangum

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))


def create_app() -> FastAPI:
    from healsync_backend.app import create_app as build_app

    return build_app()


handler = Mangum(create_app())


@http
def api(request):
    return handler(request.environ, {})
