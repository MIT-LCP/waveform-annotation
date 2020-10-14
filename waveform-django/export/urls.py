from django.urls import path
from graphene_django.views import GraphQLView
from schema import schema

urlpatterns = [
    path('graphql', GraphQLView.as_view(graphiql=False, schema=schema),
         name='graphql'),
]
