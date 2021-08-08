import graphene
from graphene_django.types import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from waveforms.models import User, Annotation, UserSettings


# View results at:
# http://localhost:8000/waveform-annotation/graphql?query={all_users{edges{node{username,join_date}}}}
class UserType(DjangoObjectType):
    class Meta:
        model = User
        filter_fields = ['username', 'join_date']
        interfaces = (graphene.relay.Node, )


# View results at:
# http://localhost:8000/waveform-annotation/graphql?query={all_annotations{edges{node{user{username},record,event,decision,comments,decision_date}}}}
class AnnotationType(DjangoObjectType):
    class Meta:
        model = Annotation
        user = graphene.Field(UserType)
        filter_fields = ['user', 'record', 'event', 'decision',
                         'comments', 'decision_date']
        interfaces = (graphene.relay.Node, )


# View results at:
# http://localhost:8000/waveform-annotation/graphql?query={all_user_settings{edges{node{user{username},fig_height,fig_width,margin_left,margin_top,margin_right,margin_bottom,grid_color,sig_color,sig_thickness,ann_color,grid_delta_major,max_y_labels,n_ekg_sigs,down_sample_ekg,down_sample,time_range_min,time_range_max,window_size_min,window_size_max}}}}
class UserSettingsType(DjangoObjectType):
    class Meta:
        model = UserSettings
        user = graphene.Field(UserType)
        filter_fields = ['user', 'fig_height', 'fig_width', 'margin_left',
                         'margin_top', 'margin_right', 'margin_bottom',
                         'grid_color', 'sig_color', 'sig_thickness',
                         'ann_color', 'grid_delta_major', 'max_y_labels',
                         'n_ekg_sigs', 'down_sample_ekg', 'down_sample',
                         'time_range_min', 'time_range_max',
                         'window_size_min', 'window_size_max']
        interfaces = (graphene.relay.Node, )


class Query(graphene.ObjectType):
    all_users = DjangoFilterConnectionField(UserType)
    all_annotations = DjangoFilterConnectionField(AnnotationType)
    all_user_settings = DjangoFilterConnectionField(UserSettingsType)
