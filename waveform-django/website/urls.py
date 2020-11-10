from django.conf.urls import include
from django.urls import path
from django.http import HttpResponse

from website import views


urlpatterns = [
    # Account creation and handling pages
	path('register/', views.register_page, name='register'),
	path('login/', views.login_page, name='login'),
	path('logout/', views.logout_user, name='logout'),
    # Waveform annotator dashboard
    path('waveforms/', include('waveforms.urls')),
    # GraphQL API interface
    path('', include('export.urls')),
    # Robots.txt for crawlers
    path('robots.txt', lambda x: HttpResponse('User-Agent: *\Allow: /',
        content_type='text/plain'), name='robots_file'),
]
