import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from waveforms.forms import GraphSettings, InviteUserForm
from waveforms.models import Annotation, InvitedEmails, User, UserSettings
from website.settings import base


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
    user = User.objects.get(username=request.user.username)
    dash_context = {
        'set_record': {'value': set_record},
        'set_event': {'value': set_event}
    }
    return render(request, 'waveforms/home.html', {'user': user,
        'dash_context': dash_context})

@login_required
def admin_console(request):
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
    user = User.objects.get(username=request.user.username)
    if not user.is_admin:
        return redirect('waveform_published_home')

    invite_user_form = InviteUserForm()

    if request.method == 'POST':
        if 'invite_user' in request.POST:
            invite_user_form = InviteUserForm(request.POST)
            if invite_user_form.is_valid():
                invite_user_form.save(
                    from_email = 'help@waveform-annotation.com',
                    request = request
                )
                messages.success(request,
                    f'User was successfully invited.')
            else:
                messages.error(request,
                    f"""An error occurred. User was not successfully
                    contacted.""")

    # Find the files
    BASE_DIR = base.BASE_DIR
    FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
    FILE_LOCAL = os.path.join('record-files')
    PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)

    # Get the record files
    project_options = os.listdir(PROJECT_PATH)
    all_projects = [p for p in project_options if os.path.isdir(os.path.join(PROJECT_PATH, p))]

    # Hold all of the annotation information
    all_records = {}
    conflict_anns = {}
    unanimous_anns = {}
    all_anns = {}
    for project in all_projects:
        records_path = os.path.join(PROJECT_PATH, project,
                                    base.RECORDS_FILE)
        with open(records_path, 'r') as f:
            all_records[project] = f.read().splitlines()

        # Get all the annotations
        all_annotations = Annotation.objects.filter(project=project)
        records = [a.record for a in all_annotations]
        events = [a.event for a in all_annotations]

        conflict_anns[project] = {}
        unanimous_anns[project] = {}
        all_anns[project] = {}

        # Get the events
        for rec in all_records[project]:
            records_path = os.path.join(PROJECT_PATH, project, rec,
                                        base.RECORDS_FILE)
            with open(records_path, 'r') as f:
                all_events = f.read().splitlines()
            all_events = [e for e in all_events if '_' in e]
            # Add annotations by event
            temp_conflict_anns = []
            temp_unanimous_anns = []
            temp_all_anns = []
            for evt in all_events:
                if (rec in records) and (evt in events):
                    same_anns = Annotation.objects.filter(
                        project=project, record=rec, event=evt)
                    if len(set([a.decision for a in same_anns])) > 1:
                        for ann in same_anns:
                            temp_conflict_anns.append([ann.user.username,
                                                    ann.event,
                                                    ann.decision,
                                                    ann.comments,
                                                    ann.decision_date])
                    else:
                        for ann in same_anns:
                            temp_unanimous_anns.append([ann.user.username,
                                                        ann.event,
                                                        ann.decision,
                                                        ann.comments,
                                                        ann.decision_date])
                else:
                    temp_all_anns.append(['-', evt, '-', '-', '-'])
            # Get the completion stats for each record
            if temp_conflict_anns != []:
                conflict_anns[project][rec] = temp_conflict_anns
            if temp_unanimous_anns != []:
                unanimous_anns[project][rec] = temp_unanimous_anns
            if temp_all_anns != []:
                all_anns[project][rec] = temp_all_anns

    # Categories to display for the annotations
    categories = [
        'user',
        'event',
        'decision',
        'comments',
        'decision_date'
    ]

    # Get all the current and invited users
    all_users = User.objects.all()
    invited_users = InvitedEmails.objects.all()

    return render(request, 'waveforms/admin_console.html', {'user': user,
        'invited_users': invited_users, 'categories': categories,
        'all_projects': all_projects, 'conflict_anns': conflict_anns,
        'unanimous_anns': unanimous_anns, 'all_anns': all_anns,
        'all_users': all_users, 'invite_user_form': invite_user_form})

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
    records_path = os.path.join(PROJECT_PATH, base.PROJECT_FOLDER,
                                base.RECORDS_FILE)
    with open(records_path, 'r') as f:
        all_records = f.read().splitlines()

    # Get all the annotations for the requested user
    user = User.objects.get(username=request.user)
    completed_annotations = Annotation.objects.filter(
        user=user, project=base.PROJECT_FOLDER)
    completed_records = [a.record for a in completed_annotations]
    completed_events = [a.event for a in completed_annotations]

    # Hold all of the annotation information
    total_anns = 0
    completed_anns = {}
    incompleted_anns = {}

    for rec in all_records:
        # Get the events
        records_path = os.path.join(PROJECT_PATH, base.PROJECT_FOLDER, rec,
                                    base.RECORDS_FILE)
        with open(records_path, 'r') as f:
            temp_events = f.read().splitlines()
        temp_events = [e for e in temp_events if '_' in e]
        total_anns += len(temp_events)

        # Add annotations by event
        temp_completed_anns = []
        temp_incompleted_anns = []
        for evt in temp_events:
            if (rec in completed_records) and (evt in completed_events):
                ann = completed_annotations[completed_events.index(evt)]
                temp_completed_anns.append([ann.event,
                                            ann.decision,
                                            ann.comments,
                                            ann.decision_date])
            else:
                temp_incompleted_anns.append([evt, '-', '-', '-'])

        # Get the completion stats for each record
        if temp_completed_anns != []:
            progress_stats = '{}/{}'.format(len(temp_completed_anns),
                                            len(temp_completed_anns))
            temp_completed_anns.insert(0, progress_stats)
            completed_anns[rec] = temp_completed_anns
        if temp_incompleted_anns != []:
            progress_stats = '0/{}'.format(len(temp_incompleted_anns))
            temp_incompleted_anns.insert(0, progress_stats)
            incompleted_anns[rec] = temp_incompleted_anns

    # Categories to display for the annotations
    categories = [
        'event',
        'decision',
        'comments',
        'decision_date'
    ]

    all_anns_frac = f'{len(completed_annotations)}/{total_anns}'

    return render(request, 'waveforms/annotations.html', {'user': user,
        'all_anns_frac': all_anns_frac, 'categories': categories,
        'completed_anns': completed_anns,
        'incompleted_anns': incompleted_anns})

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
    user = User.objects.get(username=request.user)
    try:
        annotation = Annotation.objects.get(
            user = user,
            project = base.PROJECT_FOLDER,
            record = set_record,
            event = set_event
        )
        annotation.delete()
    except Annotation.DoesNotExist:
        pass
    return render_annotations(request)

@login_required
def viewer_tutorial(request):
    """
    Render waveform tutorial page.

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for hosting the tutorial.

    """
    user = User.objects.get(username=request.user)
    return render(request, 'waveforms/tutorial.html', {'user': user})

@login_required
def viewer_settings(request):
    """
    Change the settings for the waveform viewer.

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for hosting the change settings form.

    """
    user = User.objects.get(username=request.user)
    try:
        user_settings = UserSettings.objects.get(user=user)
    except UserSettings.DoesNotExist:
        user_settings = UserSettings(user=request.user)

    if request.method == 'POST':
        if 'change_settings' in request.POST:
            settings_form = GraphSettings(user=user, data=request.POST,
                                                instance=user_settings)
            if settings_form.is_valid():
                settings_form.clean()
                settings_form.save()
                return redirect('waveform_published_home')
            else:
                messages.error(request, 'Invalid submission. See errors below.')
        elif 'reset_default' in request.POST:
            settings_form = GraphSettings(user=user, instance=user_settings)
            settings_form.reset_default()
            return redirect('waveform_published_home')
    else:
        settings_form = GraphSettings(user=user, instance=user_settings)

    return render(request, 'waveforms/settings.html', {'user': user,
        'settings_form': settings_form})
