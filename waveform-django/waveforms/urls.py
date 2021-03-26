from django.urls import path, include
from waveforms.dash_apps.finished_apps import waveform_vis

from waveforms import views


urlpatterns = [
    path('django_plotly_dash/', include('django_plotly_dash.urls')),
    path('', views.waveform_published_home, name='waveform_published_home'),
    path('<set_record>/<set_event>/', views.waveform_published_home, name='waveform_published_specific'),
    path('admin_console/', views.admin_console, name='admin_console'),
    path('annotations/', views.render_annotations, name='render_annotations'),
    path('annotations/delete/<set_record>/<set_event>/', views.delete_annotation, name='delete_annotation'),
    path('tutorial/', views.viewer_tutorial, name='viewer_tutorial'),
    path('settings/', views.viewer_settings, name='viewer_settings'),
]
