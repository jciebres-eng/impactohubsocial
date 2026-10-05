"""Ponto de entrada ASGI: ``uvicorn impacto.main:app``."""
from .app import create_app

app = create_app()
