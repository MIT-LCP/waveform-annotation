from collections import Counter, defaultdict
from itertools import chain
from pathlib import Path
from datetime import timedelta
from operator import itemgetter
import os
import csv
import random as rd
import pandas as pd

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.core.paginator import Paginator
from django.http import *
from django.shortcuts import redirect, render
from django.utils import timezone
from django.db import IntegrityError
from django.db.models import Count

from waveforms.forms import GraphSettings, InviteUserForm
from waveforms.models import Annotation, InvitedEmails, User, UserSettings, WaveformEvent
from website.settings import base


def load_waveforms():
    """
    Read in each waveform in record-files and create WaveformEvent objects.
    """
    record_folder = Path(base.HEAD_DIR)/'record-files'
    project_list = [p for p in base.ALL_PROJECTS if p not in base.BLACKLIST]
    for project in project_list:
        project_path = record_folder/project
        record_file = project_path/base.RECORDS_FILE
        with open(record_file, 'r') as f:
            record_list = f.read().splitlines()
        
        for record in record_list:
            record_path = project_path/record
            event_file = record_path/base.RECORDS_FILE
            with open(event_file, 'r') as f:
                event_list = f.read().splitlines()
            for event in event_list:
                try:
                    WaveformEvent.objects.create(project=project, record=record, event=event)
                except IntegrityError:
                    pass


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
    csv_path = Path(base.HEAD_DIR)/'record-files'/project_folder/base.ASSIGNMENT_FILE
    with open(csv_path, 'w', newline='', encoding='utf-8') as csv_file:
        csvwriter = csv.writer(csv_file)
        csvwriter.writerow(['Events', 'Users Assigned'])
        for event,user in csv_data.items():
            if user:
                row = [event]
                if type(user) is str:
                    row.extend({user})
                else:
                    row.extend(set(user))
                csvwriter.writerows([row])


def get_all_assignments(project_folder):
    """
    Return a dictionary that holds events as keys and a list assigned to users
    as values, based on the assignment CSV file as well as completed
    annotations.

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

    anns = Annotation.objects.filter(
        project=project_folder, is_adjudication=False).values_list(*['event','user__username'])
    for ann in anns:
        if not csv_data.get(ann[0]):
            csv_data[ann[0]] = [ann[1]]
        elif ann[1] not in csv_data[ann[0]]:
            csv_data[ann[0]].append(ann[1])
    return csv_data


def get_practice_anns(ann):
    """
    Filter Annotation object to only include events in practice set.

    Parameters
    ----------
    ann : Annotation object
        The object to be filtered.

    Returns
    -------
    ann: Annotation object
        The object after it has been filtered.

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
            try:
                next(csvreader)
                for row in csvreader:
                    names = []
                    for val in row[1:]:
                        if val:
                            names.append(val)
                    if user.username in names:
                        event_list.append(row[0])
            except StopIteration:
                pass

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
    user = User.objects.get(username=request.user)
    
    user_saved = [waveform.pk for waveform in user.get_waveforms(annotation='saved')]
    user_unannotated = [waveform.pk for waveform in user.get_waveforms(annotation='unannotated')]
    user_annotations = [waveform.pk for waveform in user.get_waveforms(annotation='annotated')]
    all_waveforms = user_saved + user_unannotated + user_annotations

    if len(all_waveforms) == 0:
        return redirect('current_assignment')

    if set_project and set_record and set_event:
        try:
            waveform = WaveformEvent.objects.get(project=set_project, record=set_record, event=set_event)
            if user not in waveform.annotators.all() and user.is_admin == False:
                return HttpResponseForbidden('<h1>You do not have access to this waveform</h1>')
        except WaveformEvent.DoesNotExist:
            return HttpResponseNotFound('<h1>Waveform not found</h1>')
        
        page_index = all_waveforms.index(waveform.pk)
    
    else:
        page_index = 0
    
    dash_context = {
        'is_adjudicator': {'value': False},
        'set_pageid': {'value': page_index},
        'page_order': {'value': all_waveforms},
    }

    return render(request, 'waveforms/home.html', {'user': user,
                                                   'dash_context': dash_context})


@login_required
def admin_console(request):
    """
    Render all saved annotations to allow edits.

    Parameters
    ----------
    N/A

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
            all_anns_keys = [
                'user__username', 'project', 'record', 'event', 'decision',
                'comments', 'decision_date', 'is_adjudication'
            ]
            all_anns = list(Annotation.objects.values(*all_anns_keys))
            all_anns = [
                a for a in all_anns if not (base.PRACTICE_SET.get(a['project']) and \
                    base.PRACTICE_SET.get(a['project']).get(a['event'])) 
            ]
            csv_columns = ['username', 'project', 'record', 'event',
                           'decision', 'comments', 'date', 'is_adjudication']
            all_anns = {csv_columns[i]: [d.get(k) for d in all_anns] for i,k in enumerate(all_anns_keys)}
            all_anns['decision'] = [str(d) for d in all_anns['decision']]
            csv_df = pd.DataFrame.from_dict(all_anns)
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
            user.waveforms.clear()
            
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
        elif 'add_annotator' in request.POST:
            new_annotator = User.objects.get(
                username__exact=request.POST['add_annotator']
            )
            new_annotator.is_annotator = True
            new_annotator.practice_status = 'ED'

            for proj, events in base.PRACTICE_SET.items():
                for event in events:
                    try:
                        Annotation.objects.get(user=new_annotator, project=proj,
                                            event=event,
                                            is_adjudication=False).delete()
                    except Annotation.DoesNotExist:
                        pass
            new_annotator.save()            
        elif 'remove_annotator' in request.POST:
            new_annotator = User.objects.get(
                username__exact=request.POST['remove_annotator']
            )
            new_annotator.is_annotator = False
            new_annotator.practice_status = 'BG'
            new_annotator.entrance_score = 'N/A'
            new_annotator.save()
        return redirect('admin_console')
            

    # # Find the files
    # BASE_DIR = base.BASE_DIR
    # FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
    # FILE_LOCAL = os.path.join('record-files')
    # PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)

    # # Hold all of the annotation information
    # all_records = {}
    # conflict_anns = {}
    # unanimous_anns = {}
    # all_anns = {}
    # for project in base.ALL_PROJECTS:
    #     records_path = os.path.join(PROJECT_PATH, project,
    #                                 base.RECORDS_FILE)
    #     with open(records_path, 'r') as f:
    #         all_records[project] = f.read().splitlines()

    #     # Get all the annotations
    #     all_annotations = Annotation.objects.filter(
    #         project=project).values_list(*['record','event'])
    #     records = [a[0] for a in all_annotations]
    #     events = [a[1] for a in all_annotations]

    #     conflict_anns[project] = defaultdict(dict)
    #     unanimous_anns[project] = defaultdict(dict)
    #     all_anns[project] = defaultdict(dict)

    #     # Get the events
    #     for rec in all_records[project]:
    #         records_path = os.path.join(PROJECT_PATH, project, rec,
    #                                     base.RECORDS_FILE)
    #         with open(records_path, 'r') as f:
    #             all_events = f.read().splitlines()
    #         all_events = [e for e in all_events if '_' in e]
    #         for evt in all_events:
    #             # Add annotations by event
    #             temp_conflict_anns = []
    #             temp_unanimous_anns = []
    #             temp_all_anns = []
    #             if (rec in records) and (evt in events):
    #                 same_anns = Annotation.objects.filter(
    #                     project=project, record=rec, event=evt
    #                 ).values_list(
    #                     *['decision', 'user__username', 'comments',
    #                       'decision_date', 'is_adjudication']
    #                 )
    #                 if len(set([a[0] for a in same_anns])) > 1:
    #                     for ann in same_anns:
    #                         temp_conflict_anns.append([ann[1], ann[0], ann[2],
    #                                                    ann[3], ann[4]])
    #                 else:
    #                     for ann in same_anns:
    #                         temp_unanimous_anns.append([ann[1], ann[0], ann[2],
    #                                                     ann[3], ann[4]])
    #             else:
    #                 temp_all_anns.append(['-', '-', '-', '-', '-'])
                
    #             # Get the completion stats for each record
    #             if temp_conflict_anns != []:
    #                 conflict_anns[project][rec][evt] = temp_conflict_anns
    #             if temp_unanimous_anns != []:
    #                 unanimous_anns[project][rec][evt] = temp_unanimous_anns
    #             if temp_all_anns != []:
    #                 all_anns[project][rec][evt] = temp_all_anns
        
    #     conf_page_num = request.GET.get(f"{project}_conflicts")
    #     unan_page_num = request.GET.get(f"{project}_unanimous")
    #     unfi_page_num = request.GET.get(f"{project}_unfinished")

    #     page_conflict = Paginator(tuple(conflict_anns[project].items()), 3).get_page(conf_page_num)
    #     page_unanimous = Paginator(tuple(unanimous_anns[project].items()), 3).get_page(unan_page_num)
    #     page_unfinished = Paginator(tuple(all_anns[project].items()), 3).get_page(unfi_page_num)
        
    #     conflict_anns[project] = page_conflict
    #     unanimous_anns[project] = page_unanimous
    #     all_anns[project] = page_unfinished

    #     if not page_conflict:
    #         del conflict_anns[project]
    #     if not unanimous_anns[project]:
    #         del unanimous_anns[project]
    #     if not all_anns[project]:
    #         del all_anns[project]

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
                   'categories': categories, 'all_projects': base.ALL_PROJECTS,
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
    N/A

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
    # Do not include rejected annotations
    non_adjudicated_anns = Annotation.objects.filter(
        is_adjudication=False, decision__in=['True', 'False', 'Uncertain']
    ).order_by(
        '-decision_date'
    ).values(
        'project', 'record', 'event'
    )
    all_info = [tuple(ann.values()) for ann in non_adjudicated_anns]
    unique_anns = Counter(all_info).keys()
    ann_counts = Counter(all_info).values()
    # Get completed annotations (should be two but I guess could be more if
    # glitch or old data)
    completed_anns = [c[0] for c in list(zip(unique_anns,ann_counts)) if c[1]>=2]

    # Find out which ones are conflicting
    conflicting_anns = []
    # Collect the unfinished adjudications
    incomplete_adjudications = []
    for c in completed_anns:
        # Get all the annotations for this event
        all_anns = Annotation.objects.filter(
            project=c[0], record=c[1], event=c[2]
        )
        is_adjudicated = True in [a.is_adjudication for a in all_anns]
        if not is_adjudicated:
            # Make sure the annotations are complete
            current_anns = all_anns.filter(is_adjudication=False).values_list('decision', flat=True)
            is_conflicting = len(set(current_anns)) >= 2
            # Make sure there are conflicting decisions and no adjudications already
            if is_conflicting:
                conflicting_anns.append(c)
                # Add the unfinished adjudications
                temp_anns = all_anns.values_list(
                    'project', 'record', 'event', 'user__username',
                    'decision', 'comments', 'decision_date'
                )
                incomplete_adjudications.append([list(ann) for ann in temp_anns])

    # Get info of all adjudicated annotations
    adjudicated_anns = Annotation.objects.filter(
        is_adjudication=True
    ).order_by(
        '-decision_date'
    ).values_list(
        'project', 'record', 'event'
    )
    # Collect the finished adjudications
    complete_adjudications = []
    for current_ann in adjudicated_anns:
        all_anns = Annotation.objects.filter(
            project=current_ann[0], record=current_ann[1], event=current_ann[2]
        ).values_list(
            'project', 'record', 'event', 'user__username', 'decision',
            'comments', 'decision_date'
        )
        complete_adjudications.append([list(ann) for ann in all_anns])

    search = {}
    if request.GET.get('record'):
        # TODO: only works if > 0 of each adjudication
        all_inc_recs = [v[0][1] for v in incomplete_adjudications]
        all_com_recs = [v[0][1] for v in complete_adjudications]
        results = {
            'com' : [complete_adjudications[i] for i,x in enumerate(all_com_recs) if x==request.GET['record']],
            'inc' : [incomplete_adjudications[i] for i,x in enumerate(all_inc_recs) if x==request.GET['record']]
        }
        if list(results.values()) == [None, None]:
            messages.error(request, 'Record not found')
        else:
            search = {k:v for k,v in results.items() if v}

    # TODO: let the user decide the max annotations per page?
    n_complete = len(complete_adjudications)
    complete_page_num = request.GET.get('complete_page')
    if complete_page_num == 'all':
        pag_complete = Paginator(tuple(complete_adjudications), len(complete_adjudications))
    else:
        pag_complete = Paginator(tuple(complete_adjudications), 5)
    complete_page = pag_complete.get_page(complete_page_num)
    complete_adjudications = complete_page

    n_incomplete = len(incomplete_adjudications)
    incomplete_page_num = request.GET.get('incomplete_page')
    if incomplete_page_num == 'all':
        pag_incomplete = Paginator(tuple(incomplete_adjudications), len(incomplete_adjudications))
    else:
        pag_incomplete = Paginator(tuple(incomplete_adjudications), 5)
    incomplete_page = pag_incomplete.get_page(incomplete_page_num)
    incomplete_adjudications = incomplete_page

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
                   'categories': categories, 'search': search,
                   'n_complete': n_complete, 'n_incomplete': n_incomplete,
                   'complete_page': complete_page,
                   'incomplete_page': incomplete_page,
                   'incomplete_adjudications': incomplete_adjudications,
                   'complete_adjudications': complete_adjudications})


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
def current_assignment(request):
    """
    Display a list of all waveforms assigned to and completed by user.

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for displaying the annotations.

    """
    # Get all the waveforms for the requested user
    user = User.objects.get(username=request.user)
    
    waveform_list = [ 
        user.get_annotations(saved=True),
        user.get_annotations(),
        user.get_waveforms(annotation='unannotated'),
    ]

    waveform_values = [w.values_list('project', 'record') for w in waveform_list]

    page_numbers = [
        request.GET.get('saved_page'),
        request.GET.get('annotated_page'),
        request.GET.get('unannotated_page'),
    ]

    page_info = []
    display_values = []

    for i in range(len(waveform_values)):
        if page_numbers[i]:        
            if page_numbers[i].isdigit():
                paginated_list = Paginator(waveform_values[i], 3)
                results = paginated_list.get_page(int(page_numbers[i]))
            else:
                paginated_list = Paginator(waveform_values[i], len(waveform_values[i]))
                results = paginated_list.get_page(1)
        else:
            paginated_list = Paginator(waveform_values[i], 3)
            results = paginated_list.get_page(1)
        
        page_info.append(results)

        proj_list = []
        rec_list = []
        for result in results.object_list:
            proj_list.append(result[0])
            rec_list.append(result[1])
        display_values.append(waveform_list[i].filter(project__in=proj_list, record__in=rec_list))
    
    categories = [
        'Event',
        'Decision',
        'Comments',
        'Decision Date'
    ]

    progress = f"{len(waveform_values[1])}/{len(waveform_values[0]) + len(waveform_values[1]) + len(waveform_values[2])}"

    if request.method == 'POST':
        # Create a new assignment for current user
        if 'new_assignment' in request.POST:
            load_waveforms()
            num_events = int(request.POST['num_events'])
            
            # Get waveforms not assigned to user, and not already assigned to max number of annotators
            available_waveforms = WaveformEvent.objects.\
                exclude(annotators=user).\
                annotate(num_annotators=Count('annotators')).\
                filter(num_annotators__lt=base.NUM_ANNOTATORS)
            
            # First assign user to waveforms that have already been assigned to others
            annotated_waveforms = available_waveforms.\
                filter(num_annotators__gt=0).\
                order_by('-num_annotators')
                
            for w in annotated_waveforms:
                if num_events == 0:
                    break
                else:
                    w.annotators.add(user)
                    num_events -= 1

            if num_events > 0:
                # If there are still events left, randomly assign user to unassigned waveforms
                unannotated_waveforms = available_waveforms.\
                    filter(annotators=None).\
                    order_by('?')
                
                for w in unannotated_waveforms:
                    if num_events == 0:
                        break
                    else:
                        w.annotators.add(user)
                        num_events -= 1

            if num_events > 0:
                num_events = int(request.POST['num_events']) - num_events
                messages.error(
                    request, f'Not enough events remaining. You have been given {num_events} events'
                )
            
            user.date_assigned = timezone.now()
            user.save()
            return redirect('current_assignment')

    return render(request, 'waveforms/annotations.html',
                  {'user': user, 'min_assigned': base.MIN_ASSIGNED, 'progress': progress,
                   'categories': categories, 'unannotated_waveforms': display_values[2],
                   'saved_waveforms': display_values[0], 'annotated_waveforms': display_values[1],
                   'page_info': page_info})


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
    return current_assignment(request)


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
            user=user, is_adjudication=False
        ).exclude(
            decision='Save for Later'
        ).values_list(
            'decision_date__date', 'decision'
        )
        num_today = 0
        num_week = 0
        num_month = 0
        num_all = 0
        num_true = 0
        num_false = 0
        for ann in user_anns:
            if ann[0] >= one_day:
                num_today += 1
            if ann[0] >= one_week:
                num_week += 1
            if ann[0] >= one_month:
                num_month += 1
            if ann[1] == 'True':
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

    # Get number of all events
    record_dir = Path(base.HEAD_DIR)/'record-files'
    project_list = [p for p in base.ALL_PROJECTS if p not in base.BLACKLIST]

    all_annotations = Annotation.objects.all()
    ann_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for ann in all_annotations:
        proj = ann.project
        rec = ann.record
        evt = ann.event
        is_adj = ann.is_adjudication
        decision = ann.decision
        ann_counts[proj][rec][evt].append((decision, is_adj))

    num_events = 0
    no_anns = 0
    one_ann = 0
    unan_true = 0
    unan_false = 0
    unan_uncertain = 0
    unan_reject = 0
    conflict = 0
    true_adj = 0
    false_adj = 0
    uncertain_adj = 0
    reject_adj = 0
    for project in project_list:
        project_dir = record_dir/project
        record_dirs = project_dir/base.RECORDS_FILE
        with open(record_dirs, 'r') as f:
            record_list = f.read().splitlines()
        record_list = [project_dir/r for r in record_list]
        for record in record_list:
            record_file = record/base.RECORDS_FILE
            try:
                with open(record_file, 'r') as f:
                    events = f.read().splitlines()[1:]
            except FileNotFoundError:
                continue

            for event in events:
                num_events += 1
                anns = ann_counts[project][record.stem][event]
                adj = [a for a in anns if a[1]]

                if not adj:
                    if len(anns) == 0:
                        no_anns += 1
                    elif len(anns) == 1:
                        one_ann += 1
                    elif len(anns) == 2:
                        if (anns[0][0] == 'True') and (anns[1][0] == 'True'):
                            unan_true += 1
                        elif (anns[0][0] == 'False') and (anns[1][0] == 'False'):
                            unan_false += 1
                        elif (anns[0][0] == 'Uncertain') and (anns[1][0] == 'Uncertain'):
                            unan_uncertain += 1
                        elif 'Reject' in [anns[0][0], anns[1][0]]:
                            # Annotation is rejected if only one person thinks
                            # it should be
                            unan_reject += 1
                        else:
                            conflict += 1
                else:
                    decision = adj[0][0]
                    if decision == 'True':
                        true_adj += 1
                    elif decision == 'False':
                        false_adj += 1
                    elif decision == 'Uncertain':
                        uncertain_adj += 1
                    elif decision == 'Reject':
                        reject_adj += 1

    return render(request, 'waveforms/leaderboard.html',
                  {'user': current_user, 'glob_today': glob_today,
                   'glob_week': glob_week, 'glob_month': glob_month,
                   'glob_all': glob_all, 'glob_true': glob_true,
                   'glob_false': glob_false, 'user_today': user_today,
                   'user_week': user_week, 'user_month': user_month,
                   'user_all': user_all, 'user_true': user_true,
                   'user_false': user_false, 'one_ann': one_ann,
                   'unan_true': unan_true, 'unan_false': unan_false,
                   'unan_uncertain': unan_uncertain, 'unan_reject': unan_reject,
                   'true_adj': true_adj, 'false_adj': false_adj,
                   'uncertain_adj': uncertain_adj, 'reject_adj': reject_adj,
                   'conflict': conflict, 'no_anns': no_anns,
                   'num_events': num_events})


@login_required
def practice_test(request):
    """
    Request practice set of events.

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for assigning practice events.

    """
    user = User.objects.get(username=request.user)

    results = {}
    correct = 0
    total = 0

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
            return redirect('current_assignment')

        if 'submit-practice' in request.POST:
            if user.practice_status != 'BG':
                raise PermissionError()
            user.practice_status = 'CO'
            if user.is_annotator == False:
                user.entrance_score = f"{correct}/{total}"
            user.save()
            # user.entrance_score = 
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
            return redirect('current_assignment')

    return render(request, 'waveforms/practice.html',
                  {'user': user, 'results': results, 'total': total,
                   'correct': correct})



@login_required
def assessment(request):
    """
    Configures and displays events for entry assessment.

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for enabling entry assessment.

    """
    user = User.objects.get(username=request.user)

    results = {}
    correct = 0
    total = 0

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
            return redirect('current_assignment')

        if 'submit-practice' in request.POST:
            if user.practice_status != 'BG':
                raise PermissionError()
            user.practice_status = 'CO'
            if user.is_annotator == False:
                user.entrance_score = f"{correct}/{total}"
            user.save()
            # user.entrance_score = 
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
            return redirect('current_assignment')

    return render(request, 'waveforms/assessment_info.html',
                  {'user': user, 'results': results, 'total': total,
                   'correct': correct})


@login_required
def assessment_results(request, annotator):
    """
    Displays the results of a user's assessment.

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for enabling entry assessment.

    """
    current_user = User.objects.get(username=request.user)
    annotator = User.objects.get(username=annotator)
    if current_user.is_admin == False:
        return HttpResponseNotFound('<h1>Page not found</h1>')
    
    results = {}
    correct = 0
    total = 0

    for project,events in base.PRACTICE_SET.items():
        results[project] = {}
        for event,answer in events.items():
            try:
                user_response = Annotation.objects.get(
                    user=annotator, project=project, event=event,
                    is_adjudication=False).decision
            except Annotation.DoesNotExist:
                user_response = None
            record = event[:event.index('_')]
            results[project][event] = (record, str(answer), user_response)
            total += 1
            correct = correct + 1 if str(answer) == user_response else correct + 0


    return render(request, 'waveforms/assessment_result.html', {'user': current_user, 'annotator': annotator, 
                                                                'results':results, 'correct':correct,'total':total})


@login_required
def viewer_overview(request):
    """
    Render the project overview page.

    Parameters
    ----------
    N/A

    Returns
    ----------
    N/A : HTML page / template variable
        HTML webpage responsible for hosting the overview.
    """
    user = User.objects.get(username=request.user)
    return render(request, 'waveforms/overview.html', {'user': user})

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
