import os
from collections import Counter, defaultdict
from datetime import timedelta
from operator import itemgetter
import csv
import random as rd

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import connection
import pandas as pd

from waveforms.forms import GraphSettings, InviteUserForm
from waveforms.models import Annotation, InvitedEmails, User, UserSettings
from website.settings import base


def user_rank(global_ranks, username):
    """
    Return location of current user in leaderboard category.

    Parameters
    ----------
    global_ranks : list : list
        Contains info of users in a specific category.
    username : str
        Name of user to find in leaderboard.

    Returns
    -------
    user_data : list : int, int
        The rank of the user in the specified category and the number of
        annotations made.

    """
    user_data = []
    for info in global_ranks:
        if info[0] == username:
            user_data.append([global_ranks.index(info) + 1, info[1]])
    return user_data


def update_assignments(csv_data, project_folder):
    """
    Update the assignment CSV file to include new assignments.

    Parameters
    ----------
    csv_data : str : [str]
        A map where event names are the keys and lists of assigned users are
        the values.
    project_folder : str
        The name of the folder whose assignments will be updated.

    Returns
    -------
    N/A

    """
    # Find the files

    BASE_DIR = base.BASE_DIR
    FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
    FILE_LOCAL = os.path.join('record-files')
    PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)
    csv_path = os.path.join(PROJECT_PATH, project_folder, base.ASSIGNMENT_FILE)

    with open(csv_path, 'w', newline='', encoding='utf-8') as csv_file:
        csvwriter = csv.writer(csv_file)
        csvwriter.writerow(['Events', 'Users Assigned'])
        for event,user in csv_data.items():
            if user:
                row = [event]
                if type(user) is str:
                    row.extend([user])
                else:
                    row.extend(user)
                csvwriter.writerows([row])


def get_all_assignments(project_folder):
    """
    Return a dictionary that holds events as keys and a list assigned to users
    as values, based on the assignment CSV file as well as completed annotations.

    Parameters
    ----------
    project_folder : str
        The name of the folder whose assignments will be retrieved.

    Returns
    -------
    N/A : dict
        Data within the CSV file.

    """
    # Find the files
    BASE_DIR = base.BASE_DIR
    FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
    FILE_LOCAL = os.path.join('record-files')
    PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)
    csv_path = os.path.join(PROJECT_PATH, project_folder, base.ASSIGNMENT_FILE)

    csv_data = {}
    with open(csv_path, 'r') as csv_file:
        csvreader = csv.reader(csv_file, delimiter=',')
        try:
            next(csvreader)
        except StopIteration:
            return csv_data
        for row in csvreader:
            names = []
            for val in row[1:]:
                if val:
                    names.append(val)
            try:
                csv_data[row[0]] = names
            except IndexError:
                break

    anns = Annotation.objects.filter(project=project_folder)
    for ann in anns:
        if not csv_data.get(ann.event):
            csv_data[ann.event] = [ann.user.username]
        elif ann.user.username not in csv_data[ann.event]:
            csv_data[ann.event].append(ann.user.username)

    return csv_data


def get_practice_anns(ann):
    """
    Filter Annotation object to only include events in practice set

    Parameters
    ----------
    ann : Annotation object
        Object to be filtered

    Returns
    -------
    ann: Annotation object
    """
    events_per_proj = [list(events.keys()) for events in base.PRACTICE_SET.values()]
    events = []
    for i in events_per_proj:
        events += i
    return ann.filter(
        project__in=[key for key in base.PRACTICE_SET.keys()],
        event__in=events
    )


def get_user_events(user, project_folder):
    """
    Get the events assigned to a user in the CSV file.

    Parameters
    ----------
    user : User
        The User whose events will be retrieved.
    project_folder : str
        The project used to retrieve the events.

    Returns
    -------
    N/A: list
        List of events assigned to the user.

    """
    # Find the files
    BASE_DIR = base.BASE_DIR
    FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
    FILE_LOCAL = os.path.join('record-files')
    PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)

    if user.practice_status != 'ED':
        events_per_proj = [list(events.keys()) for events in base.PRACTICE_SET.values()]
        events = []
        for i in events_per_proj:
            events += i
        return events
    else:
        csv_path = os.path.join(PROJECT_PATH, project_folder,
                                base.ASSIGNMENT_FILE)
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
        user_ann = Annotation.objects.filter(user=user,
                                             project=project_folder,
                                             is_adjudication=False)
        if user.practice_status != 'ED':
            user_ann = get_practice_anns(user_ann)
        event_list += [a.event for a in user_ann if a.event not in event_list]
    return event_list


@login_required
def waveform_published_home(request, set_project='', set_record='', set_event=''):
    """
    Render waveform main page for published databases.

    Parameters
    ----------
    set_project: string, optional
        Preset project dropdown values used for page load
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
        'is_adjudicator': {'value': False},
        'set_project': {'value': set_project},
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

    ann_to_csv_form = forms.Form()
    invite_user_form = InviteUserForm()
    add_admin_form = forms.Form()
    remove_admin_form = forms.Form()

    if request.method == 'POST':
        if 'ann_to_csv' in request.POST:
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
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=all_anns.csv'
            csv_df.to_csv(path_or_buf=response, sep=',', index=False)
            return response
        elif 'invite_user' in request.POST:
            invite_user_form = InviteUserForm(request.POST)
            if invite_user_form.is_valid():
                invite_user_form.save(
                    from_email=base.EMAIL_FROM,
                    request=request
                )
                messages.success(request,
                                 f'User was successfully invited.')
            else:
                messages.error(request,
                               f"""An error occurred. User was not successfully
                    contacted.""")
        elif 'end_assignment' in request.POST:
            user = User.objects.get(username=request.POST['user_info'])
            for project in base.ALL_PROJECTS:
                csv_data = get_all_assignments(project)
                for event, names in csv_data.items():
                    if user.username in names:
                        try:
                            Annotation.objects.get(user=user, project=project,
                                                   event=event,
                                                   is_adjudication=False)
                        except Annotation.DoesNotExist:
                            csv_data[event].remove(user.username)
                update_assignments(csv_data, project)
            return redirect('admin_console')
        elif 'add_admin' in request.POST:
            new_admin = User.objects.get(
                username__exact=request.POST['add_admin']
            )
            new_admin.is_admin = True
            new_admin.save()
        elif 'remove_admin' in request.POST:
            new_admin = User.objects.get(
                username__exact=request.POST['remove_admin']
            )
            new_admin.is_admin = False
            new_admin.save()
        elif 'add_adjudicator' in request.POST:
            new_adjudicator = User.objects.get(
                username__exact=request.POST['add_adjudicator']
            )
            new_adjudicator.is_adjudicator = True
            new_adjudicator.save()
        elif 'remove_adjudicator' in request.POST:
            new_adjudicator = User.objects.get(
                username__exact=request.POST['remove_adjudicator']
            )
            new_adjudicator.is_adjudicator = False
            new_adjudicator.save()

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
            conflict_anns[project][rec] = {}
            unanimous_anns[project][rec] = {}
            all_anns[project][rec] = {}
            records_path = os.path.join(PROJECT_PATH, project, rec,
                                        base.RECORDS_FILE)
            with open(records_path, 'r') as f:
                all_events = f.read().splitlines()
            all_events = [e for e in all_events if '_' in e]
            for evt in all_events:
                # Add annotations by event
                temp_conflict_anns = []
                temp_unanimous_anns = []
                temp_all_anns = []
                if (rec in records) and (evt in events):
                    same_anns = Annotation.objects.filter(
                        project=project, record=rec, event=evt)
                    if len(set([a.decision for a in same_anns])) > 1:
                        for ann in same_anns:
                            temp_conflict_anns.append([ann.user.username,
                                                       ann.decision,
                                                       ann.comments,
                                                       ann.decision_date,
                                                       ann.is_adjudication])
                    else:
                        for ann in same_anns:
                            temp_unanimous_anns.append([ann.user.username,
                                                        ann.decision,
                                                        ann.comments,
                                                        ann.decision_date,
                                                        ann.is_adjudication])
                else:
                    temp_all_anns.append(['-', '-', '-', '-', '-'])
                # Get the completion stats for each record
                if temp_conflict_anns != []:
                    conflict_anns[project][rec][evt] = temp_conflict_anns
                if temp_unanimous_anns != []:
                    unanimous_anns[project][rec][evt] = temp_unanimous_anns
                if temp_all_anns != []:
                    all_anns[project][rec][evt] = temp_all_anns

    # Categories to display for the annotations
    categories = [
        'user',
        'decision',
        'comments',
        'decision_date',
        'is_adjudication'
        ''
    ]

    # Get all the current and invited users
    all_users = User.objects.all()
    invited_users = InvitedEmails.objects.all()

    return render(request, 'waveforms/admin_console.html',
                  {'user': user, 'invited_users': invited_users,
                   'categories': categories, 'all_projects': all_projects,
                   'conflict_anns': conflict_anns,
                   'unanimous_anns': unanimous_anns, 'all_anns': all_anns,
                   'all_users': all_users, 'ann_to_csv_form': ann_to_csv_form,
                   'invite_user_form': invite_user_form,
                   'add_admin_form': add_admin_form,
                   'remove_admin_form': remove_admin_form})


@login_required
def adjudicator_console(request, set_project='', set_record='', set_event=''):
    """
    Render all conflicting annotations to allow adjudication.

    Parameters
    ----------
    set_project: string, optional
        Preset project dropdown values used for page load
    set_record : string, optional
        Preset record dropdown values used for page load.
    set_event : string, optional
        Preset event dropdown values used for page load.

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for displaying the conflicting annotations
        and their adjudication platform.

    """
    user = User.objects.get(username=request.user.username)
    if not user.is_adjudicator:
        return redirect('waveform_published_home')

    dash_context = {
        'set_project': {'value': set_project},
        'set_record': {'value': set_record},
        'set_event': {'value': set_event}
    }

    return render(request, 'waveforms/adjudicator_console.html',
                  {'user': user, 'dash_context': dash_context})


@login_required
def render_adjudications(request):
    """
    Render all saved adjudications to allow edits.

    Parameters
    ----------
    N/A : N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for displaying the adjudications.

    """
    # Make sure the user has access
    user = User.objects.get(username=request.user.username)
    if not user.is_adjudicator:
        return redirect('waveform_published_home')

    # Get info of all non-adjudicated annotations assuming non-unique event names
    non_adjudicated_anns = Annotation.objects.filter(is_adjudication=False)
    all_info = [(a.project, a.record, a.event) for a in non_adjudicated_anns]
    unique_anns = Counter(all_info).keys()
    ann_counts = Counter(all_info).values()
    # Get completed annotations (should be two but I guess could be more if
    # glitch or old data)
    completed_anns = [c[0] for c in list(zip(unique_anns,ann_counts)) if c[1]>=2]

    # Find out which ones are conflicting
    conflicting_anns = []
    for c in completed_anns:
        # Get all the annotations for this event
        all_anns = Annotation.objects.filter(
            project=c[0], record=c[1], event=c[2]
        )
        is_adjudicated = True in [a.is_adjudication for a in all_anns]
        # Make sure the annotations are complete
        current_anns = all_anns.filter(is_adjudication=False)
        is_conflicting = len(set([a.decision for a in current_anns])) >= 2
        # Make sure there are conflicting decisions and no adjudications already
        if is_conflicting and not is_adjudicated:
            conflicting_anns.append(c)

    # Get info of all adjudicated annotations
    adjudicated_anns = Annotation.objects.filter(is_adjudication=True)
    # Collect the unfinished adjudications
    unfinished_adjudications = []
    for info in conflicting_anns:
        all_anns = Annotation.objects.filter(
            project=info[0], record=info[1], event=info[2]
        )
        temp_anns = []
        for ann in all_anns:
            temp_anns.append([ann.project,
                              ann.record,
                              ann.event,
                              ann.user.username,
                              ann.decision,
                              ann.comments,
                              ann.decision_date])
        unfinished_adjudications.append(temp_anns)
    # Collect the finished adjudications
    finished_adjudications = []
    for ann in adjudicated_anns:
        all_anns = Annotation.objects.filter(
            project=ann.project, record=ann.record, event=ann.event
        )
        temp_anns = []
        for ann in all_anns:
            temp_anns.append([ann.project,
                              ann.record,
                              ann.event,
                              ann.user.username,
                              ann.decision,
                              ann.comments,
                              ann.decision_date])
        finished_adjudications.append(temp_anns)

    categories = [
        'event',
        'user',
        'decision',
        'comments',
        'decision_date'
    ]
    total_anns = len(adjudicated_anns) + len(conflicting_anns)
    all_anns_frac = f'{len(adjudicated_anns)}/{total_anns}'

    return render(request, 'waveforms/adjudications.html',
                  {'user': user, 'all_anns_frac': all_anns_frac,
                   'categories': categories,
                   'unfinished_adjudications': unfinished_adjudications,
                   'finished_adjudications': finished_adjudications})


@login_required
def delete_adjudication(request, set_project, set_record, set_event):
    """
    Delete adjudications.

    Parameters
    ----------
    set_record : string
        Desired record used to identify adjudications to delete.
    set_event : string
        Desired event used to identify adjudications to delete.

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for rendering the adjudications.

    """
    try:
        # Should only be one adjudication per project, record, and event
        adjudication = Annotation.objects.get(
            project=set_project,
            record=set_record,
            event=set_event,
            is_adjudication=True
        )
        adjudication.delete()
    except Annotation.DoesNotExist:
        pass
    return render_adjudications(request)


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

    # Get all the annotations for the requested user
    user = User.objects.get(username=request.user)
    # All annotations
    all_annotations = Annotation.objects.filter(user=user, is_adjudication=False)

    if user.practice_status != 'ED':
        events_per_proj = [list(events.keys()) for events in base.PRACTICE_SET.values()]
        events = []
        for i in events_per_proj:
            events += i
        all_annotations = all_annotations.filter(
            project__in=[key for key in base.PRACTICE_SET.keys()],
            event__in=events
        )

    # Completed annotations
    completed_annotations = all_annotations.filter(
        decision__in=['True', 'False', 'Uncertain']
    )
    completed_records = [a.record for a in completed_annotations]
    completed_events = [a.event for a in completed_annotations]
    # Saved annotations
    saved_annotations = all_annotations.filter(decision='Save for Later')
    saved_records = [a.record for a in saved_annotations]
    saved_events = [a.event for a in saved_annotations]
    save_warning = len(saved_annotations) > 0

    # Hold all of the annotation information
    completed_anns = {}
    saved_anns = {}
    incompleted_anns = {}

    # Get list where each element is a list of records from a project folder
    all_projects = base.ALL_PROJECTS if user.practice_status == 'ED' else list(base.PRACTICE_SET.keys())
    # Get all user records
    user_records = {}
    # Get all user events
    user_events = {}
    if user.is_admin and user.practice_status == 'ED':
        for project in all_projects:
            user_events[project] = []
            records_path = os.path.join(PROJECT_PATH, project,
                                        base.RECORDS_FILE)
            with open(records_path, 'r') as f:
                user_records[project] = f.read().splitlines()
            for record in user_records[project]:
                event_path = os.path.join(PROJECT_PATH, project, record,
                                        base.RECORDS_FILE)
                with open(event_path, 'r') as f:
                    user_events[project] += f.read().splitlines()
            user_events[project] = [e for e in user_events[project] if '_' in e]
    else:
        for project in all_projects:
            user_events[project] = get_user_events(user, project) if user.practice_status == 'ED' \
                else list(base.PRACTICE_SET[project].keys())
        for project in all_projects:
            events = user_events[project]
            user_records[project] = []
            for evt in events:
                rec = evt[:evt.find('_')]
                if rec not in user_records[project]:
                    user_records[project].append(rec)

    # Get the total number of annotations
    total_anns = sum([len(user_events[k]) for k in user_events.keys()])

    # Display user events
    for project,record_list in user_records.items():
        for rec in sorted(record_list):
            temp_events = [e for e in user_events[project] if e[:e.find('_')] == rec]

            # Add annotations by event
            temp_completed_anns = []
            temp_saved_anns = []
            temp_incompleted_anns = []
            for evt in temp_events:
                if (rec in completed_records) and (evt in completed_events):
                    ann = completed_annotations[completed_events.index(evt)]
                    temp_completed_anns.append([ann.event,
                                                ann.decision,
                                                ann.comments,
                                                ann.decision_date])
                elif (rec in saved_records) and (evt in saved_events):
                    ann = saved_annotations[saved_events.index(evt)]
                    temp_saved_anns.append([ann.event,
                                                ann.decision,
                                                ann.comments,
                                                ann.decision_date])
                else:
                    temp_incompleted_anns.append([evt, '-', '-', '-'])

            # Get the completion stats for each record
            if temp_completed_anns != []:
                progress_stats = f'{len(temp_completed_anns)}/{len(temp_events)}'
                temp_completed_anns.insert(0, progress_stats)
                temp_completed_anns.insert(1, project)
                completed_anns[rec] = temp_completed_anns
            if temp_saved_anns != []:
                progress_stats = f'{len(temp_saved_anns)}/{len(temp_events)}'
                temp_saved_anns.insert(0, progress_stats)
                temp_saved_anns.insert(1, project)
                saved_anns[rec] = temp_saved_anns
            if temp_incompleted_anns != []:
                progress_stats = f'{len(temp_incompleted_anns)}/{len(temp_events)}'
                temp_incompleted_anns.insert(0, progress_stats)
                temp_incompleted_anns.insert(1, project)
                incompleted_anns[rec] = temp_incompleted_anns

    search = {}
    if request.GET.get('record'):
        results = {
            'save': saved_anns.get(request.GET['record']),
            'inc' : incompleted_anns.get(request.GET['record']),
            'com' :completed_anns.get(request.GET['record'])
        }

        if list(results.values()) == [None, None, None]:
            messages.error(request, 'Record not found')
        else:
            num = len(results['com'][2:]) if results['com'] else 0
            den = sum([len(r[2:]) for r in list(results.values()) if r])
            frac = f'{num}/{den}'

            results = {key:val for key,val in results.items() if val}
            dataset = list(results.values())[0][1]

            search = [frac, dataset]
            for r in list(results.values()):
                search.extend(r[2:])
            search = {request.GET['record'] : search}

    saved_page_num = request.GET.get('saved_page')
    if saved_page_num == 'all':
        pag_saved = Paginator(tuple(saved_anns.items()), len(saved_anns.items()))
    else:
        pag_saved = Paginator(tuple(saved_anns.items()), 5)
    saved_page = pag_saved.get_page(saved_page_num)
    saved_anns = dict(saved_page)

    complete_page_num = request.GET.get('complete_page')
    if complete_page_num == 'all':
        pag_complete = Paginator(tuple(completed_anns.items()), len(completed_anns.items()))
    else:
        pag_complete = Paginator(tuple(completed_anns.items()), 5)
    complete_page = pag_complete.get_page(complete_page_num)
    completed_anns = dict(complete_page)

    incomplete_page_num = request.GET.get('incomplete_page')
    if incomplete_page_num == 'all':
        pag_incomplete = Paginator(tuple(incompleted_anns.items()), len(incompleted_anns.items()))
    else:
        pag_incomplete = Paginator(tuple(incompleted_anns.items()), 5)
    incomplete_page = pag_incomplete.get_page(incomplete_page_num)
    incompleted_anns = dict(incomplete_page)

    categories = [
        'event',
        'decision',
        'comments',
        'decision_date'
    ]
    all_anns_frac = f'{len(completed_annotations)}/{total_anns}'
    finished_assignment = len(completed_annotations) == total_anns

    if request.method == 'POST':
        if 'new_assignment' in request.POST:
            available_projects = [p for p in all_projects if p not in base.BLACKLIST]
            num_events = int(request.POST['num_events'])
            assigned_events = {}
            unassigned_events = {}

            for project in available_projects:
                assigned_events[project] = get_all_assignments(project)

                records_path = os.path.join(PROJECT_PATH, project, base.RECORDS_FILE)
                with open(records_path, 'r') as f:
                    record_list = f.read().splitlines()
                proj_events = []
                for record in record_list:
                    event_path = os.path.join(PROJECT_PATH, project, record,
                                              base.RECORDS_FILE)
                    with open(event_path, 'r') as f:
                        proj_events += f.read().splitlines()
                proj_events = [e for e in proj_events if '_' in e]

                for event in proj_events:
                    if event not in assigned_events[project].keys():
                        try:
                            unassigned_events[project].append(event)
                        except KeyError:
                            unassigned_events[project] = [event]

            # First assign events that already have one user assigned
            for project,assignments in assigned_events.items():
                for event,assignees in assignments.items():
                    if len(assignees) == 1:
                        assignees.append(user.username)
                        assigned_events[project][event] = assignees
                        num_events -= 1
                        if num_events == 0:
                            break
                    if num_events == 0:
                            break

            # No event is only assigned to one user, randomly assign new events
            while num_events:
                try:
                    rand_project = rd.choice(available_projects)
                except IndexError:
                    # No project has free events
                    break
                
                if unassigned_events.get(rand_project):
                    rand_event = rd.choice(unassigned_events[rand_project])
                    assigned_events[rand_project][rand_event] = [user.username]
                    unassigned_events[rand_project].remove(rand_event)
                    num_events -= 1
                else:
                    available_projects.remove(rand_project)

            for proj,data in assigned_events.items():
                update_assignments(data, proj)

            # Update the user's assignment start date
            user.date_assigned = timezone.now()
            user.save()
            return redirect('render_annotations')

    return render(request, 'waveforms/annotations.html',
                  {'user': user, 'all_anns_frac': all_anns_frac,
                   'categories': categories, 'completed_anns': completed_anns,
                   'complete_page':complete_page, 'search': search,
                   'saved_anns': saved_anns, 'saved_page':saved_page,
                   'incompleted_anns': incompleted_anns,
                   'incomplete_page': incomplete_page,
                   'finished_assignment': finished_assignment,
                   'remaining': total_anns - len(completed_annotations),
                   'save_warning': save_warning})


@login_required
def delete_annotation(request, set_project, set_record, set_event):
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
            project=set_project,
            record=set_record,
            event=set_event,
            is_adjudication=False
        )
        annotation.delete()
    except Annotation.DoesNotExist:
        pass
    return render_annotations(request)


@login_required()
def leaderboard(request):
    current_user = User.objects.get(username=request.user.username)
    all_users = User.objects.all()
    now = timezone.now().date()
    one_day = now - timedelta(days=1)
    one_week = now - timedelta(days=7)
    one_month = now - timedelta(days=30)

    # Get global leaderboard info
    glob_today = []
    glob_week = []
    glob_month = []
    glob_all = []
    glob_true = []
    glob_false = []
    for user in all_users:
        user_anns = Annotation.objects.filter(
            user=user, is_adjudication=False).exclude(decision='Save for Later')
        num_today = 0
        num_week = 0
        num_month = 0
        num_all = 0
        num_true = 0
        num_false = 0
        for ann in user_anns:
            if ann.decision_date.date() >= one_day:
                num_today += 1
            if ann.decision_date.date() >= one_week:
                num_week += 1
            if ann.decision_date.date() >= one_month:
                num_month += 1
            if ann.decision == "True":
                num_true += 1
            else:
                num_false += 1
            num_all += 1
        glob_today.append([user.username, num_today])
        glob_week.append([user.username, num_week])
        glob_month.append([user.username, num_month])
        glob_all.append([user.username, num_all])
        glob_true.append([user.username, num_true])
        glob_false.append([user.username, num_false])

    glob_today = sorted(glob_today, key=itemgetter(1), reverse=True)
    glob_week = sorted(glob_week, key=itemgetter(1), reverse=True)
    glob_month = sorted(glob_month, key=itemgetter(1), reverse=True)
    glob_all = sorted(glob_all, key=itemgetter(1), reverse=True)
    glob_true = sorted(glob_true, key=itemgetter(1), reverse=True)
    glob_false = sorted(glob_false, key=itemgetter(1), reverse=True)

    # Extract User stats
    username = current_user.username
    user_today = user_rank(glob_today, username)
    user_week = user_rank(glob_week, username)
    user_month = user_rank(glob_month, username)
    user_all = user_rank(glob_all, username)
    user_true = user_rank(glob_true, username)
    user_false = user_rank(glob_false, username)

    # Get number of events completed and in progress
    ann_dict = defaultdict(int)
    all_anns = Annotation.objects.filter(
        is_adjudication=False).exclude(decision='Save for Later')
    two_anns = 0
    for ann in all_anns:
        key = f'{ann.project} {ann.record} {ann.event}'
        ann_dict[key] += 1
        two_anns = two_anns + 1 if ann_dict[key] == 2 else two_anns
    one_ann = f'{(len(ann_dict) - two_anns):,}'
    # Get the number of annotations which conflict
    conflict_anns = 0
    all_ann_tuples = set([(a.record,a.event) for a in all_anns])
    for rec,evt in all_ann_tuples:
        current_rec_evt = all_anns.filter(record=rec, event=evt)
        if len(current_rec_evt) > 1:
            if len(set([a.decision for a in current_rec_evt])) > 1:
                conflict_anns += 1
    complete = f'{(two_anns-conflict_anns):,}'

    return render(request, 'waveforms/leaderboard.html',
                  {'user': current_user, 'glob_today': glob_today,
                   'glob_week': glob_week, 'glob_month': glob_month,
                   'glob_all': glob_all, 'glob_true': glob_true,
                   'glob_false': glob_false, 'user_today': user_today,
                   'user_week': user_week, 'user_month': user_month,
                   'user_all': user_all, 'user_true': user_true,
                   'user_false': user_false, 'one_ann': one_ann,
                   'complete': complete, 'conflict_anns': conflict_anns})


@login_required
def practice_test(request):
    """
    Request practice set of events

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for assigning practice events

    """
    user = User.objects.get(username=request.user)

    results = {}
    correct = 0
    total = 0
    if user.practice_status == 'CO':
        for project,events in base.PRACTICE_SET.items():
            results[project] = {}
            for event,answer in events.items():
                try:
                    user_response = Annotation.objects.get(
                        user=user, project=project, event=event,
                        is_adjudication=False).decision
                except Annotation.DoesNotExist:
                    user_response = None
                results[project][event] = (str(answer), user_response)
                total += 1
                correct = correct + 1 if str(answer) == user_response else correct + 0

    if request.method == 'POST':
        if 'start-practice' in request.POST:
            if user.practice_status != 'ED':
                raise PermissionError()
            user.practice_status = 'BG'
            user.save()
            return redirect('render_annotations')

        if 'submit-practice' in request.POST:
            if user.practice_status != 'BG':
                raise PermissionError()
            user.practice_status = 'CO'
            user.save()
            return redirect('practice_test')

        if 'end-practice' in request.POST:
            # Delete practice events
            for proj, events in base.PRACTICE_SET.items():
                for event in events:
                    try:
                        Annotation.objects.get(user=user, project=proj,
                                                   event=event,
                                                   is_adjudication=False).delete()
                    except Annotation.DoesNotExist:
                        pass
            user.practice_status = 'ED'
            user.save()
            return redirect('render_annotations')

    return render(request, 'waveforms/practice.html',
                  {'user': user, 'results': results, 'total': total,
                   'correct': correct})


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

    return render(request, 'waveforms/settings.html',
                  {'user': user, 'settings_form': settings_form})
