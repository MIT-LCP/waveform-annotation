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
from django.core.exceptions import FieldError
from django.db.models import Count, Q

from waveforms.forms import GraphSettings, InviteUserForm
from waveforms.models import Annotation, InvitedEmails, User, UserSettings, WaveformEvent, Bookmark
from website.settings import base


def update_practice_set():
    """
    Sets waveforms to practice mode. Deletes annotations for waveforms that
    are no longer in practice mode.
    """
    current_practice = set(WaveformEvent.objects.filter(is_practice=True).values_list('pk', flat=True))
    updated_practice = set()
    for event in base.PRACTICE_SET:
        print(f"evt {event}")
        try:
            waveform = WaveformEvent.objects.get(project=event[0], record=event[1], event=event[2])
            updated_practice.add(waveform.pk)
            waveform.is_practice = True
            waveform.save()
        except WaveformEvent.DoesNotExist:
            pass
    
    difference = current_practice.difference(updated_practice)
    
    remove_sets = WaveformEvent.objects.filter(pk__in=difference)
    for waveform in remove_sets:
        waveform.is_practice = False
        waveform.save()
        Annotation.objects.filter(waveform=waveform).delete()

    print(f"DEBUG: {current_practice} | {updated_practice} | {difference}")


def load_waveforms():
    """
    Read in each waveform in record-files and create WaveformEvent objects.
    """
    record_folder = Path(base.HEAD_DIR)/'record-files'
    project_list = [p for p in base.ALL_PROJECTS if p not in base.BLACKLIST]
    for project in project_list:
        project_path = record_folder/project
        record_file = project_path/base.RECORDS_FILE
        try:
            with open(record_file, 'r') as f:
                record_list = f.read().splitlines()
        except FileNotFoundError as e:
            print(f"{e}")
            continue
        
        for record in record_list:
            record_path = project_path/record
            event_file = record_path/base.RECORDS_FILE
            try:
                with open(event_file, 'r') as f:
                    event_list = f.read().splitlines()
            except FileNotFoundError as e:
                print(f"{e}")
                continue
            for event in event_list:
                header_path = record_path/f"{event}.mat"
                if header_path.is_file():
                    try:
                        WaveformEvent.objects.create(project=project, record=record, event=event)
                    except IntegrityError:
                        pass
                else:
                    pass

    update_practice_set()



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
        'adjudication_mode': {'value': False},
        'admin_mode': {'value': False},
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
            waveforms = WaveformEvent.objects.filter(annotators=user, is_practice=False).exclude(annotation__user=user)
            [w.annotators.remove(user) for w in waveforms]
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
            Annotation.objects.filter(user=new_annotator, waveform__is_practice=True).delete()
            new_annotator.save()            
        elif 'remove_annotator' in request.POST:
            new_annotator = User.objects.get(
                username__exact=request.POST['remove_annotator']
            )
            new_annotator.is_annotator = False
            new_annotator.practice_status = 'BG'
            new_annotator.entrance_score = 'N/A'
            new_annotator.save()
        elif 'load_waveforms' in request.POST:
            load_waveforms()
        elif 'update_practice_set' in request.POST:
            update_practice_set()
        return redirect('admin_console')
            
    
    all_waveforms = WaveformEvent.objects.filter(is_practice=False)
    waveform_list = [
        all_waveforms.exclude(decision__in=['None', 'Conflict']), # Final Decisions
        all_waveforms.filter(decision='Conflict'), # Conflicts
        all_waveforms.filter(decision='None'), # In Progress
    ]

    waveform_values = [list(set(waveforms.values_list('project', 'record'))) for waveforms in waveform_list]

    page_numbers = [
        request.GET.get('final_decisions_page'),
        request.GET.get('conflicts_page'),
        request.GET.get('in_progress_page'),
    ]

    page_info = []
    display_values = []
    max_values_per_page = 3

    for i in range(len(waveform_values)):
        if page_numbers[i]:        
            if page_numbers[i].isdigit():
                paginated_list = Paginator(waveform_values[i], max_values_per_page)
                results = paginated_list.get_page(int(page_numbers[i]))
            else:
                paginated_list = Paginator(waveform_values[i], len(waveform_values[i]))
                results = paginated_list.get_page(1)
        else:
            paginated_list = Paginator(waveform_values[i], max_values_per_page)
            results = paginated_list.get_page(1)
        
        page_info.append(results)
        proj_list = []
        rec_list = []
        for result in results.object_list:
            proj_list.append(result[0])
            rec_list.append(result[1])
        
        display_values.append(waveform_list[i].filter(project__in=proj_list, record__in=rec_list))

    # Categories to display for the annotations
    categories = [
        'Annotator Name',
        'Decision',
        'Comments',
        'Decision Date'
    ]

    # Get all the current and invited users
    all_users = User.objects.all()
    invited_users = InvitedEmails.objects.all()

    return render(request, 'waveforms/admin_console.html',
                  {'user': user, 'invited_users': invited_users,
                   'categories': categories, 'all_users': all_users,
                    'ann_to_csv_form': ann_to_csv_form, 'invite_user_form': invite_user_form,
                    'add_admin_form': add_admin_form, 'remove_admin_form': remove_admin_form,
                    'final_decisions': display_values[0], 'conflicts': display_values[1],
                    'in_progress': display_values[2], 'page_info': page_info,
                   })


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
    user = User.objects.get(username=request.user)

    if user.is_adjudicator == False:
        return HttpResponseForbidden('<h1>You do not have access to this page</h1>')

    all_waveforms = WaveformEvent.objects.filter(is_practice=False)
    
    bookmarked = all_waveforms.filter(bookmark__is_adjudication=True)
    conflicts = all_waveforms.filter(decision='Conflict')
    adjudicated = all_waveforms.filter(annotation__is_adjudication=True)

    bookmarked = [bookmark.pk for bookmark in bookmarked]
    conflicts = [waveform.pk for waveform in conflicts]
    adjudicated = [waveform.pk for waveform in adjudicated]

    all_waveforms = bookmarked + conflicts + adjudicated

    if len(all_waveforms) == 0:
        return redirect('render_adjudications')

    if set_project and set_record and set_event:
        try:
            waveform = WaveformEvent.objects.get(project=set_project, record=set_record, event=set_event)
            if waveform.pk not in all_waveforms:
                return HttpResponseForbidden('<h1>This Waveform does not yet require adjudication</h1>')
        except WaveformEvent.DoesNotExist:
            return HttpResponseNotFound('<h1>Waveform not found</h1>')
        
        page_index = all_waveforms.index(waveform.pk)
    
    else:
        page_index = 0
    
    dash_context = {
        'adjudication_mode': {'value': True},
        'admin_mode': {'value': False},
        'set_pageid': {'value': page_index},
        'page_order': {'value': all_waveforms},
    }

    return render(request, 'waveforms/home.html', {'user': user,
                                                   'dash_context': dash_context})



@login_required
def admin_waveform_viewer(request, set_project='', set_record='', set_event=''):
    """
    Allow admins to view any specified waveform

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
    user = User.objects.get(username=request.user)

    if user.is_admin == False:
        return HttpResponseForbidden('<h1>You do not have access to this page</h1>')

    all_waveforms = [w.pk for w in WaveformEvent.objects.filter(is_practice=False)]

    if len(all_waveforms) == 0:
        return redirect('admin_console')

    if set_project and set_record and set_event:
        try:
            waveform = WaveformEvent.objects.get(project=set_project, record=set_record, event=set_event)
        except WaveformEvent.DoesNotExist:
            return HttpResponseNotFound('<h1>Waveform not found</h1>')
        
        page_index = all_waveforms.index(waveform.pk)
    
    else:
        page_index = 0
    
    dash_context = {
        'adjudication_mode': {'value': False},
        'admin_mode': {'value': True},
        'set_pageid': {'value': page_index},
        'page_order': {'value': all_waveforms},
    }

    return render(request, 'waveforms/home.html', {'user': user,
                                                   'dash_context': dash_context})


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
        return HttpResponseForbidden('<h1>You do not have access to this feature.</h1>')

    max_annotated = WaveformEvent.objects.annotate(num_annotations=Count('annotation')).filter(num_annotations__gte=base.NUM_ANNOTATORS)
    unadjudicated = max_annotated.filter(num_annotations=base.NUM_ANNOTATORS).annotate(num_diff_decisions=Count('annotation__decision', distinct=True))
    conflicts = unadjudicated.filter(num_diff_decisions__gt=1)

    waveform_list = [
        conflicts.filter(bookmark__is_adjudication=True), # Bookmarked
        conflicts.exclude(bookmark__is_adjudication=True), # Conflicts w/o bookmark
        max_annotated.filter(annotation__is_adjudication=True) # Adjudicated
    ]
    
    waveform_values = [list(set(waveforms.values_list('project', 'record'))) for waveforms in waveform_list]

    page_numbers = [
        request.GET.get('bookmarked_page'),
        request.GET.get('conflicts_page'),
        request.GET.get('adjudicated_page'),
    ]

    page_info = []
    display_values = []
    max_values_per_page = 3

    for i in range(len(waveform_values)):
        if page_numbers[i]:        
            if page_numbers[i].isdigit():
                paginated_list = Paginator(waveform_values[i], max_values_per_page)
                results = paginated_list.get_page(int(page_numbers[i]))
            else:
                paginated_list = Paginator(waveform_values[i], len(waveform_values[i]))
                results = paginated_list.get_page(1)
        else:
            paginated_list = Paginator(waveform_values[i], max_values_per_page)
            results = paginated_list.get_page(1)
        
        page_info.append(results)
        proj_list = []
        rec_list = []
        for result in results.object_list:
            proj_list.append(result[0])
            rec_list.append(result[1])
        
        display_values.append(waveform_list[i].filter(project__in=proj_list, record__in=rec_list))

    # Categories to display for the annotations
    categories = [
        'User',
        'Decision',
        'Decision Date',
        'Comments',
    ]

    progress = f"{len(waveform_list[2])}/{len(waveform_list[0]) + len(waveform_list[1]) + len(waveform_list[2])}"
    
    return render(request, 'waveforms/adjudications.html',
                  {'user': user, 'categories': categories, 'page_info': page_info,
                    'bookmarked': display_values[0], 'conflicts': display_values[1], 
                    'adjudicated': display_values[2], 'progress': progress})


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
        waveform = WaveformEvent.objects.get(project=set_project, record=set_record, event=set_event)
        adjudication = Annotation.objects.get(waveform=waveform, is_adjudication=True)
        adjudication.delete()
    except Annotation.DoesNotExist:
        waveform = WaveformEvent.objects.get(project=set_project, record=set_record, event=set_event)
        bookmark = Bookmark.objects.get(waveform=waveform, is_adjudication=True)
        bookmark.delete()
    except WaveformEvent.DoesNotExist:
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

    max_values_per_page = 5
    
    waveform_list = [ 
        user.get_bookmarks(),
        user.get_annotations(),
        user.get_waveforms(annotation='unannotated'),
    ]

    waveform_values = [
        list(set(waveform_list[0].values_list('waveform__project', 'waveform__record'))),
        list(set(waveform_list[1].values_list('waveform__project', 'waveform__record'))),
        list(set(waveform_list[2].values_list('project', 'record'))),
    ] 
    
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
                paginated_list = Paginator(waveform_values[i], max_values_per_page)
                results = paginated_list.get_page(int(page_numbers[i]))
            else:
                paginated_list = Paginator(waveform_values[i], len(waveform_values[i]))
                results = paginated_list.get_page(1)
        else:
            paginated_list = Paginator(waveform_values[i], max_values_per_page)
            results = paginated_list.get_page(1)
        
        page_info.append(results)
        proj_list = []
        rec_list = []
        for result in results.object_list:
            proj_list.append(result[0])
            rec_list.append(result[1])
        try:
            display_values.append(waveform_list[i].filter(waveform__project__in=proj_list, waveform__record__in=rec_list))
        except FieldError:
            display_values.append(waveform_list[i].filter(project__in=proj_list, record__in=rec_list))
    
    categories = [
        'Event',
        'Decision',
        'Comments',
        'Decision Date'
    ]

    progress = f"{len(waveform_list[1])}/{len(waveform_list[0]) + len(waveform_list[1]) + len(waveform_list[2])}"

    if request.method == 'POST':
        # Create a new assignment for current user
        if 'new_assignment' in request.POST:
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
            waveform__project=set_project,
            waveform__record=set_record,
            waveform__event=set_event,
            is_adjudication=False
        )
        annotation.delete()
    except Annotation.DoesNotExist:
        try:
            bookmark = Bookmark.objects.get(
                user=user,
                waveform__project=set_project,
                waveform__record=set_record,
                waveform__event=set_event
            )
            bookmark.delete()
        except:
            print("Passed")
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

    results = []
    correct = 0
    total = 0

    user_response = Annotation.objects.filter(user=user)

    for question in base.PRACTICE_SET:
        proj, rec, evt, ans = question
        try:
            waveform = WaveformEvent.objects.get(project=proj, record=rec, event=evt)
        except WaveformEvent.DoesNotExist:
            continue
        try:
            decision = user_response.get(waveform=waveform).decision
        except Annotation.DoesNotExist:
            decision = 'None'
        
        if decision == ans:
            correct += 1
        total += 1

        results.append(question + [decision])

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
            for question in base.PRACTICE_SET:
                proj, rec, evt, ans = question
                try:
                    waveform = WaveformEvent.objects.get(project=proj, record=rec, event=evt)
                    Annotation.objects.get(user=user, waveform=waveform).delete()
                except Annotation.DoesNotExist:
                    pass
                except WaveformEvent.DoesNotExist:
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
