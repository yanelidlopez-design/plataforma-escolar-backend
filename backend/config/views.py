from pathlib import Path
from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.views.static import serve


def serve_frontend(request: HttpRequest, path: str = '') -> HttpResponse:
    frontend_root = settings.FRONTEND_DIST_DIR
    index_file = frontend_root / 'index.html'

    if path:
        target_file = frontend_root / path
        if target_file.is_file():
            return serve(request, path, document_root=str(frontend_root))

    if index_file.is_file():
        return serve(request, 'index.html', document_root=str(frontend_root))

    # Fallback si index.html está en backend/templates
    templates_dir = settings.BACKEND_DIR / 'templates'
    if (templates_dir / 'index.html').is_file():
        return serve(request, 'index.html', document_root=str(templates_dir))

    raise Http404('El build del frontend no está disponible.')
