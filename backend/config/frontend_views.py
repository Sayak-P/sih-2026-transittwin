"""
Serve the Vite-built frontend SPA from Django.

This view reads the built `frontend/dist/index.html` and returns it for any
URL that doesn't match an API route, admin, or static-file path. This lets
us run the entire application from a single Daphne server on port 8000.
"""
from django.conf import settings
from django.http import HttpResponse, FileResponse
from django.views import View
import os


class FrontendAppView(View):
    """Serve the Vite SPA index.html for any non-API route."""

    def get(self, request, *args, **kwargs):
        # Check if the request is for a static file in the dist root (e.g. favicon.svg)
        requested_path = request.path.lstrip("/")
        dist_file = settings.FRONTEND_DIST_DIR / requested_path
        if requested_path and dist_file.is_file():
            return FileResponse(open(dist_file, "rb"))

        # Otherwise serve the SPA shell
        index_path = settings.FRONTEND_DIST_DIR / "index.html"
        if not index_path.exists():
            return HttpResponse(
                "<h1>Frontend not built</h1>"
                "<p>Run <code>cd frontend && npm run build</code> first.</p>",
                status=503,
            )

        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        response = HttpResponse(content, content_type="text/html")
        response["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
