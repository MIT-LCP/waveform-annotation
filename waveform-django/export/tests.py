from schema import Query
from django.test.testcases import TestCase
import graphene
import json

from waveforms.models import Annotation


class TestGraphQL(TestCase):

    def test_all_annotations(self):
        schema = graphene.Schema(query=Query, auto_camelcase=False)
        query_correct = """
            query {
                all_annotations {
                    project
                    record
                    decision
                    comments
                    decision_date
                }
            }
        """
        query_incorrect = """
            query {
                all_annotations {
                    project
                    record
                    decision
                    comments
                }
            }
        """
        correct_output = []
        for p in Annotation.objects.all():
            correct_output.append({
                'project': p.project,
                'record': p.record,
                'slug': p.slug,
                'decision': p.decision,
                'comments': p.comments,
                'decision_date': p.decision_date,
            })
        result_correct = schema.execute(query_correct)
        self.assertIsNone(result_correct.errors)
        result_incorrect = schema.execute(query_incorrect)
        self.assertIsNotNone(result_incorrect.errors)
        result_correct = json.loads(json.dumps(result_correct.to_dict()))['data']['all_annotations']
        matches = [i for i in result_correct if i not in correct_output]
        self.assertEqual(matches, [])
