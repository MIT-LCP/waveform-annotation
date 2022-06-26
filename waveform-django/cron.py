from datetime import datetime
import os

import pandas as pd
import pytz

from waveforms.models import Annotation
from website.settings import base


def update_annotations():
    """
    Automatically download the annotations to a CSV file as a cron job.

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A

    """
    # Update the annotation CSV file each night at midnight.
    all_anns = Annotation.objects.all()
    csv_df = pd.DataFrame.from_dict({
        'username': [a.user.username for a in all_anns],
        'project' : [a.project for a in all_anns],
        'record': [a.record for a in all_anns],
        'event': [a.event for a in all_anns],
        'decision': [a.decision for a in all_anns],
        'comments': [a.comments for a in all_anns],
        'decision_date': [str(a.decision_date) for a in all_anns],
        'is_adjudication': [a.is_adjudication for a in all_anns],
    })
    file_name = datetime.now(pytz.timezone(base.TIME_ZONE)).strftime('all-anns_%H_%M_%d_%m_%Y.csv')
    out_file = os.path.join(base.HEAD_DIR, 'backups', file_name)
    csv_df.to_csv(out_file, sep=',', index=False)
