import os
from django.conf import settings

def get_public_origin():
    return getattr(settings, "DJANGO_PUBLIC_ORIGIN", os.environ.get("DJANGO_PUBLIC_ORIGIN", "http://localhost:8000"))
