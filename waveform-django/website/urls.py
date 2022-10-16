from django.conf.urls import include
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import path

import debug_toolbar
from website import views


urlpatterns = [
    # Debug toolbar
    path('__debug__/', include(debug_toolbar.urls)),
    # Account creation and handling pages
    path('waveform-annotation/register/',
         views.register_page, name='register'),
    path('waveform-annotation/login/',
         views.login_page, name='login'),
    path('waveform-annotation/logout/',
         views.logout_user, name='logout'),
    path('waveform-annotation/password_reset/',
         views.reset_password, name='password_reset'),
    path('waveform-annotation/password_reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_done.html'),
         name='password_reset_done'),
    path('waveform-annotation/reset/<uidb64>/<token>/',
         views.change_password, name='password_reset_confirm'),
    path('waveform-annotation/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),
    # Waveform annotator dashboard
    path('', views.redirect_home),
    path('waveform-annotation/waveforms/', include('waveforms.urls')),
    # GraphQL API interface
    path('waveform-annotation/', include('export.urls')),
    # Robots.txt for crawlers
    path('waveform-annotation/robots.txt',
         lambda x: HttpResponse('User-Agent: *\Allow: /',
         content_type='text/plain'), name='robots_file'),
]
