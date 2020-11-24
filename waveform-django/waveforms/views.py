import os
import wfdb
from website.settings import base
from waveforms.models import Annotation

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def waveform_published_home(request, set_record='', set_event=''):
    """
    Render waveform main page for published databases.

    Parameters
    ----------
    set_record : string, optional
        Preset record dropdown values used for page load.
    set_event : string, optional
        Preset event dropdown values used for page load.

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for hosting the waveform plot.

    """
    dash_context = {
        'set_record': {'value': set_record},
        'set_event': {'value': set_event}
    }

    return render(request, 'waveforms/home.html',
        {'dash_context': dash_context})


@login_required
def render_annotations(request):
    """
    Render all saved annotations to allow edits.

    Parameters
    ----------
    N/A : N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for displaying the annotations.

    """
    # Find the files
    BASE_DIR = base.BASE_DIR
    FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
    FILE_LOCAL = os.path.join('record-files')
    PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)

    # Get the record files
    records_path = os.path.join(PROJECT_PATH, 'RECORDS')
    with open(records_path, 'r') as f:
        all_records = f.read().splitlines()

    # Hold all of the record and event information
    all_information = {}

    # Get the events
    for rec in all_records:
        header_path = os.path.join(PROJECT_PATH, rec, rec)
        all_events = wfdb.rdheader(header_path).seg_name
        all_events = [s for s in all_events if s != (rec+'_layout') and s != '~']
        all_information[rec] = all_events

    # Get all the annotations for the requested user
    current_user = request.user.username
    all_annotations = Annotation.objects.filter(user=current_user)
    records = [a.record for a in all_annotations]
    events = [a.event for a in all_annotations]
    all_anns = []

    for rec in all_information.keys():
        for evt in all_information[rec]:
            temp_anns = []
            if (rec in records) and (evt in events):
                ann = all_annotations[events.index(evt)]
                temp_anns.append(ann.record)
                temp_anns.append(ann.event)
                temp_anns.append(ann.decision)
                temp_anns.append(ann.comments)
                temp_anns.append(ann.decision_date)
            else:
                temp_anns.append(rec)
                temp_anns.append(evt)
                temp_anns.extend(['-', '-', '-'])
            all_anns.append(temp_anns)

    # Categories to display for the annotations
    categories = [
        'record',
        'event',
        'decision',
        'comments',
        'decision_date'
    ]

    return render(request, 'waveforms/annotations.html',
        {'categories': categories,
         'all_anns': all_anns})


@login_required
def delete_annotation(request, set_record, set_event):
    """
    Delete annotation.

    Parameters
    ----------
    set_record : string
        Desired record used to identify annotation to delete.
    set_event : string
        Desired event used to identify annotation to delete.

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for rendering the annotations.

    """
    try:
        annotation = Annotation.objects.get(
            user = request.user,
            record = set_record,
            event = set_event
        )
        annotation.delete()
    except Annotation.DoesNotExist:
        pass
    return render_annotations(request)
