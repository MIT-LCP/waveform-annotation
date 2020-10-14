import graphene
from graphene_django.types import DjangoObjectType

from waveforms.models import Annotation

# View results at:
# http://localhost:8000/graphql?query={all_annotations{project,record,decision,comments,decision_date}}
class AnnotationType(DjangoObjectType):
    class Meta:
        model = Annotation
        fields = ('project', 'record', 'decision', 'comments',
                  'decision_date')

class Query(object):
    all_annotations = graphene.List(AnnotationType)

    def resolve_all_annotations(self, info, **kwargs):
        return Annotation.objects.all()
