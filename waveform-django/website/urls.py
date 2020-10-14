from django.conf.urls import include
from django.urls import path
from django.http import HttpResponse
from django.conf.urls import handler404, handler500

from website import views


handler403 = 'website.views.error_403'
handler404 = 'website.views.error_404'
handler500 = 'website.views.error_500'


urlpatterns = [

    path('waveforms/', include('waveforms.urls')),
    path('', include('export.urls')),

    # # Custom error pages for testing
    # path('403.html', views.error_403, name='error_403'),
    # path('404.html', views.error_404, name='error_404'),
    # path('500.html', views.error_500, name='error_500'),

    # robots.txt for crawlers
    path('robots.txt', lambda x: HttpResponse("User-Agent: *\Allow: /", 
        content_type="text/plain"), name="robots_file"),
]
