import graphene
from graphene_django.types import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField

from waveforms.models import Annotation


# View results at:
# http://localhost:8000/graphql?query={all_annotations{edges{node{user,record,event,decision,comments,decision_date}}}}
class AnnotationType(DjangoObjectType):
    class Meta:
        model = Annotation
        filter_fields = ['user', 'record', 'event', 'decision',
                         'comments', 'decision_date']
        interfaces = (graphene.relay.Node, )


class Query(graphene.ObjectType):
    all_annotations = DjangoFilterConnectionField(AnnotationType)
