from django.conf import settings
from django.contrib import admin
from django.http import Http404, HttpResponse
from django.urls import include, path, re_path


def spa(request, *args, **kwargs):
    """Serve the React app for any non-API route (React Router handles the path)."""
    index = settings.BASE_DIR / "frontend_dist" / "index.html"
    if not index.exists():
        raise Http404("Frontend not built.")
    return HttpResponse(index.read_text(encoding="utf-8"), content_type="text/html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("mess.urls")),
    re_path(r"^(?!api/|admin/|static/|assets/).*$", spa),
]
