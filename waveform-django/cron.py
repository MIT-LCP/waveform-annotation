from datetime import datetime
import os

import pandas as pd

from waveforms.models import Annotation
from website.settings import base


def update_annotations():
    # Update the annotation CSV file each night at midnight.
    all_anns = Annotation.objects.filter(is_adjudication=False)
    csv_df = pd.DataFrame.from_dict({
        'username': [a.user.username for a in all_anns],
        'dataset' : [a.project for a in all_anns],
        'record': [a.record for a in all_anns],
        'event': [a.event for a in all_anns],
        'decision': [a.decision for a in all_anns],
        'comment': [a.comments for a in all_anns],
        'date': [str(a.decision_date) for a in all_anns]
    })
    file_name = datetime.now().strftime('all-anns_%H_%M_%d_%m_%Y.csv')
    out_file = os.path.join(base.HEAD_DIR, 'backups', file_name)
    csv_df.to_csv(out_file, sep=',', index=False)
