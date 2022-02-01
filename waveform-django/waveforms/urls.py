from django.urls import path, include
# Needed to render the graph
from waveforms.dash_apps.finished_apps import waveform_vis
from waveforms.dash_apps.finished_apps import waveform_vis_adjudicate

from waveforms import views


urlpatterns = [
    path('django_plotly_dash/', include('django_plotly_dash.urls')),
    path('', views.waveform_published_home, name='waveform_published_home'),
    path('<set_project>/<set_record>/<set_event>/', views.waveform_published_home, name='waveform_published_specific'),
    path('adjudicate/<set_project>/<set_record>/<set_event>/', views.adjudicator_console, name='waveform_published_specific_adjudicate'),
    path('adjudications/', views.render_adjudications, name='render_adjudications'),
    path('adjudications/delete/<set_project>/<set_record>/<set_event>/', views.delete_adjudication, name='delete_adjudication'),
    path('admin_console/', views.admin_console, name='admin_console'),
    path('adjudicator_console/', views.adjudicator_console, name='adjudicator_console'),
    path('annotations/', views.render_annotations, name='render_annotations'),
    path('annotations/delete/<set_project>/<set_record>/<set_event>/', views.delete_annotation, name='delete_annotation'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('tutorial/', views.viewer_tutorial, name='viewer_tutorial'),
    path('practice/', views.practice_test, name='practice_test'),
    path('settings/', views.viewer_settings, name='viewer_settings'),
]
