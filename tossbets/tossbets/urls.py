from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

admin.site.site_header = "TossBets Admin"
admin.site.site_title = "TossBets"
admin.site.index_title = "Control Panel"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("matches/", include("apps.matches.urls", namespace="matches")),
    path("payments/", include("apps.payments.urls", namespace="payments")),
    path("", RedirectView.as_view(pattern_name="matches:lobby"), name="home"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
