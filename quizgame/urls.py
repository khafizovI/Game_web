"""
URL configuration for quizgame project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.conf.urls.i18n import i18n_patterns
from . import views

handler400 = 'quizgame.views.bad_request'
handler403 = 'quizgame.views.permission_denied'
handler404 = 'quizgame.views.page_not_found'
handler500 = 'quizgame.views.server_error'

# Non-translated URLs
urlpatterns = [
    # Use our custom language switcher instead of Django's built-in one
    path('i18n/setlang/', views.set_language, name='set_language'),
    path('healthz/', views.healthcheck, name='healthcheck'),
    path('.well-known/appspecific/com.chrome.devtools.json', views.def_chrome_devtools_json, name='chrome_devtools_json'),
]

# Translated URLs (these will have language prefix like /en/, /ru/, /uz/)
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('quiz/', include('quiz.urls', namespace='quiz')),
    path('game/', include('game.urls', namespace='game')),
    prefix_default_language=True,  # Show prefix for default language too
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
