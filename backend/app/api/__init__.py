"""
API package initialization
"""
from fastapi import APIRouter
from .v1 import api_router

__all__ = ["api_router"]
