from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.views.static import serve


def serve_frontend(request: HttpRequest, path: str = '') -> HttpResponse:
    frontend_root = settings.FRONTEND_DIST_DIR
    index_file = frontend_root / 'index.html'
    if not index_file.is_file():
        raise Http404('El build del frontend no está disponible.')

    if path:
        try:
            return serve(request, path, document_root=str(frontend_root))
        except Http404:
            pass

    return serve(request, 'index.html', document_root=str(frontend_root))
