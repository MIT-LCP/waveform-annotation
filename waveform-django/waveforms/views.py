import os
import datetime
import csv
import wfdb
from datetime import datetime as dt
from waveforms import forms
from website.settings import base
from waveforms.models import User, Annotation, UserSettings

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.http import HttpResponse


# Find the files
BASE_DIR = base.BASE_DIR
FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
FILE_LOCAL = os.path.join('record-files')
PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)
csv_path = os.path.join(PROJECT_PATH, base.RECORDS_CSV)

def update_assignments(csv_rows):
    """
    Update the assignments csv file

    Parameters
    ----------
    csv_rows : str : [str]
        A map where event names are the keys and
        lists of assigned users are the values

    Returns
    -------
    N/A

    """

    with open(csv_path, 'w', newline='', encoding='utf-8') as csv_file:
        csvwriter = csv.writer(csv_file)
        csvwriter.writerow(['Events', 'Users Assigned'])
        for key, val in csv_rows.items():
            row = [key]
            row.extend(val)
            csvwriter.writerows([row])

def get_all_assignments():
    """
    Return a dictionary that holds events as keys and a
    list assigned users as values, based on assignment
    csv file

    Returns
    -------
    dict
        Data within csv file
    """

    csv_rows = {}
    with open(csv_path, 'r') as csv_file:
        csvreader = csv.reader(csv_file, delimiter=',')
        next(csvreader)
        for row in csvreader:
            names = []
            for val in row[1:]:
                if val:
                    names.append(val)
            csv_rows[row[0]] = names
    return csv_rows


def get_user_events(user):
    """
    Get the events assigned to a user in the CSV file

    Parameters
    ----------
    user : User
        The User whose events will be retrieved

    Returns
    -------
    list
        List of events assigned to the user
    """

    event_list = []
    with open(csv_path, 'r') as csv_file:
        csvreader = csv.reader(csv_file, delimiter=',')
        next(csvreader)
        for row in csvreader:
            names = []
            for val in row[1:]:
                if val:
                    names.append(val)
            if user.username in names:
                event_list.append(row[0])
    return event_list

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

    records_path = os.path.join(PROJECT_PATH, base.RECORDS_FILE)
    with open(records_path, 'r') as f:
        all_records = f.read().splitlines()

    # Hold all of the annotation information
    conflict_anns = {}
    unanimous_anns = {}
    all_anns = {}

    # Get all the annotations
    all_annotations = Annotation.objects.all()
    records = [a.record for a in all_annotations]
    events = [a.event for a in all_annotations]

    # Get the events
    for rec in all_records:
        with open(records_path, 'r') as f:
            all_events = f.read().splitlines()
        all_events = [e for e in all_events if '_' in e]
        # Add annotations by event
        temp_conflict_anns = []
        temp_unanimous_anns = []
        temp_all_anns = []
        for evt in all_events:
            if (rec in records) and (evt in events):
                same_anns = Annotation.objects.filter(record=rec, event=evt)
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
            conflict_anns[rec] = temp_conflict_anns
        if temp_unanimous_anns != []:
            unanimous_anns[rec] = temp_unanimous_anns
        if temp_all_anns != []:
            all_anns[rec] = temp_all_anns

    # Categories to display for the annotations
    categories = [
        'user',
        'event',
        'decision',
        'comments',
        'decision_date'
    ]

    # Get all the current users
    all_users = User.objects.all()

    # Allow admins to change assignment due dates
    if request.method == 'POST':
        if 'submit_change' in request.POST:
            user = User.objects.get(username=request.POST['user_info'])
            new_date = dt.strptime(request.POST['change_date'], '%Y-%m-%d')
            user.due_date = timezone.make_aware(new_date)
            user.save()
            return redirect('admin_console')

    overdue_users = []
    for u in all_users:
        if u.is_overdue() and u.events_remaining() > 0:
            overdue_users.append(u)
    if overdue_users:
        csv_rows = get_all_assignments()
        for u in overdue_users:
            for event, names in csv_rows.items():
                if u.username in names:
                    try:
                        Annotation.objects.get(user=u, event=event)
                    except Annotation.DoesNotExist:
                        names.remove(u.username)
        update_assignments(csv_rows)
        return redirect('admin_console')

    today = dt.strftime(timezone.now(), '%Y-%m-%d')

    return render(request, 'waveforms/admin_console.html', {'user': user,
        'categories': categories, 'conflict_anns': conflict_anns,
        'unanimous_anns': unanimous_anns, 'all_anns': all_anns,
        'all_users': all_users, 'today': today})


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

    # Get the record files
    records_path = os.path.join(PROJECT_PATH, base.RECORDS_FILE)
    with open(records_path, 'r') as f:
        all_records = f.read().splitlines()

    # Get all the annotations for the requested user
    user = User.objects.get(username=request.user)

    completed_annotations = Annotation.objects.filter(user=user)
    completed_records = [a.record for a in completed_annotations]
    completed_events = [a.event for a in completed_annotations]

    # Hold all of the annotation information
    total_anns = 0
    completed_anns = {}
    incompleted_anns = {}

    # Get assigned events and completed events from CSV
    event_list = get_user_events(user)
    for e in completed_events:
        if e not in event_list:
            event_list.append(e)

    for rec in all_records:
        # Get the events
        records_path = os.path.join(PROJECT_PATH, rec, base.RECORDS_FILE)
        with open(records_path, 'r') as f:
            temp_events = f.read().splitlines()
        temp_events = [e for e in temp_events if '_' in e and e in event_list]
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

    total_anns = len(event_list)
    all_anns_frac = f'{len(completed_annotations)}/{total_anns}'

    finished_assignment = (user.events_remaining() == 0)
    remaining = user.events_remaining()

    # End assignment if deadline has passed. Remove only unfinished events
    if user.is_overdue() and user.events_remaining() > 0:
        csv_rows = get_all_assignments()
        for event, names in csv_rows.items():
            if user.username in names:
                try:
                    Annotation.objects.get(user=user, event=event)
                except Annotation.DoesNotExist:
                    names.remove(user.username)

        update_assignments(csv_rows)
        return redirect('render_annotations')

    # Check if user requests more annotations
    if request.method == 'POST':
        if 'more_annotations' in request.POST:
            csv_rows = get_all_assignments()

            # Add events to CSV if not already present
            for rec in all_records:
                records_path = os.path.join(PROJECT_PATH, rec, base.RECORDS_FILE)
                with open(records_path, 'r') as f:
                    temp_events = f.read().splitlines()
                temp_events = [e for e in temp_events if '_' in e]
                for e in temp_events:
                    if e not in csv_rows.keys():
                        csv_rows[e] = []

            # Assign user events that have not been previously assigned to them
            completed_annotations = Annotation.objects.filter(user=user)
            completed_events = [a.event for a in completed_annotations]

            events_to_ann = int(request.POST["num_events"])
            due_date = request.POST["due_date"]

            max_ann_per_event = 2
            num_events = 0
            assigned_events = []
            for event, names_list in csv_rows.items():
                if event in completed_events:
                    continue
                can_annotate = True
                for name in names_list:
                    if name == user.username:
                        can_annotate = False
                        break
                if can_annotate and len(names_list) < max_ann_per_event:
                    names_list.append(user.username)
                    assigned_events.append(event)
                    num_events += 1
                if num_events == len(csv_rows) or num_events == events_to_ann:
                    break

            # Update CSV
            update_assignments(csv_rows)

            # Update Due Date
            due_date = dt.strptime(due_date, '%Y-%m-%d')
            user.due_date = timezone.make_aware(due_date)
            user.date_assigned = timezone.now()
            user.save()
            return redirect('render_annotations')

    # Set earliest due date to be in one week
    earliest = dt.strftime(timezone.now() + datetime.timedelta(days=7), '%Y-%m-%d')

    return render(request, 'waveforms/annotations.html', {'user': user,
        'all_anns_frac': all_anns_frac, 'categories': categories,
        'finished_assignment': finished_assignment, 'remaining': remaining,
        'completed_anns': completed_anns, 'due_date': user.due_date,
        'incompleted_anns': incompleted_anns, 'earliest': earliest})


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
            user=user,
            record=set_record,
            event=set_event
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
            settings_form = forms.GraphSettings(user=user, data=request.POST,
                                                instance=user_settings)
            if settings_form.is_valid():
                settings_form.clean()
                settings_form.save()
                return redirect('waveform_published_home')
            else:
                messages.error(request, 'Invalid submission. See errors below.')
        elif 'reset_default' in request.POST:
            settings_form = forms.GraphSettings(user=user, instance=user_settings)
            settings_form.reset_default()
            return redirect('waveform_published_home')
    else:
        settings_form = forms.GraphSettings(user=user, instance=user_settings)

    return render(request, 'waveforms/settings.html', {'user': user,
        'settings_form': settings_form})
