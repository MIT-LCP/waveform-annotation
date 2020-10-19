from django.shortcuts import render
from waveforms.models import Annotation


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
    all_annotations = Annotation.objects.all()

    categories = [
        'project',
        'record',
        'decision',
        'comments',
        'decision_date'
    ]
    values = []

    for ann in all_annotations:
        temp_values = []
        temp_values.append(ann.project)
        temp_values.append(ann.record)
        temp_values.append(ann.decision)
        temp_values.append(ann.comments)
        temp_values.append(ann.decision_date)
        values.append(temp_values)

    return render(request, 'waveforms/annotations.html',
        {'categories': categories,
         'values': values})
