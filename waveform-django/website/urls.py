from django.conf.urls import include
from django.urls import path
from django.http import HttpResponse
import debug_toolbar

from website import views


urlpatterns = [
    # Debug toolbar
    path('__debug__/', include(debug_toolbar.urls)),
    # Account creation and handling pages
	path('waveform-annotation/register/', views.register_page, name='register'),
	path('waveform-annotation/login/', views.login_page, name='login'),
	path('waveform-annotation/logout/', views.logout_user, name='logout'),
    # Waveform annotator dashboard
    path('waveform-annotation/waveforms/', include('waveforms.urls')),
    # GraphQL API interface
    path('waveform-annotation/', include('export.urls')),
    # Robots.txt for crawlers
    path('waveform-annotation/robots.txt', lambda x: HttpResponse('User-Agent: *\Allow: /',
        content_type='text/plain'), name='robots_file'),
]
