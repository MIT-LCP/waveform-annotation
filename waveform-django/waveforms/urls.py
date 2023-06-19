from django.urls import include, path
# Needed to render the graph
from waveforms.dash_apps.finished_apps import waveform_vis

from waveforms import views


urlpatterns = [
    path('django_plotly_dash/', include('django_plotly_dash.urls')),
    path('', views.waveform_published_home, name='waveform_published_home'),
    path('<set_project>/<set_record>/<set_event>/', views.waveform_published_home, name='waveform_published_specific'),
    path('adjudicate/<set_project>/<set_record>/<set_event>/', views.adjudicator_console, name='waveform_published_specific_adjudicate'),
    path('adjudications/', views.render_adjudications, name='render_adjudications'),
    path('adjudications/delete/<set_project>/<set_record>/<set_event>/', views.delete_adjudication, name='delete_adjudication'),
    path('admin_console/', views.admin_console, name='admin_console'),
    path('admin_console/view/<set_project>/<set_record>/<set_event>/', views.admin_waveform_viewer, name='admin_waveform_viewer'),
    path('adjudicator_console/', views.adjudicator_console, name='adjudicator_console'),
    path('assignment/', views.current_assignment, name='current_assignment'),
    path('annotations/delete/<set_project>/<set_record>/<set_event>/', views.delete_annotation, name='delete_annotation'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('tutorial/', views.viewer_tutorial, name='viewer_tutorial'),
    path('overview/', views.viewer_overview, name='viewer_overview'),
    path('practice/', views.practice_test, name='practice_test'),
    path('assessment-info/', views.assessment, name='assessment'),
    path('assessment-result/<annotator>/', views.assessment_results, name='assessment_result'),
    path('settings/', views.viewer_settings, name='viewer_settings'),
]
