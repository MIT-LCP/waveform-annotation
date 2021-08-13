import os
from datetime import timedelta
from operator import itemgetter
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

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
        for key, val in csv_data.items():
            row = [key]
            row.extend(val)
            csvwriter.writerows([row])


def get_all_assignments(project_folder):
    """
    Return a dictionary that holds events as keys and a list assigned to users
    as values, based on the assignment CSV file.

    Parameters
    ----------
    project_folder : str
        The name of the folder whose assignments will be retrieved.

    Returns
    -------
    N/A : dict
        Data within csv file.

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
        next(csvreader)
        for row in csvreader:
            names = []
            for val in row[1:]:
                if val:
                    names.append(val)
            try:
                csv_data[row[0]] = names
            except IndexError:
                break
    return csv_data


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
    N/A : list
        List of events assigned to the user.

    """
    # Find the files
    BASE_DIR = base.BASE_DIR
    FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
    FILE_LOCAL = os.path.join('record-files')
    PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)
    csv_path = os.path.join(PROJECT_PATH, project_folder, base.ASSIGNMENT_FILE)

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

    invite_user_form = InviteUserForm()

    if request.method == 'POST':
        if 'invite_user' in request.POST:
            invite_user_form = InviteUserForm(request.POST)
            if invite_user_form.is_valid():
                invite_user_form.save(
                    from_email='help@waveform-annotation.com',
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
                            Annotation.objects.get(user=user, project=project, event=event)
                        except Annotation.DoesNotExist:
                            names.remove(user.username)
                update_assignments(csv_data, project)
            return redirect('admin_console')

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

    return render(request, 'waveforms/admin_console.html',
                  {'user': user, 'invited_users': invited_users,
                   'categories': categories, 'all_projects': all_projects,
                   'conflict_anns': conflict_anns,
                   'unanimous_anns': unanimous_anns, 'all_anns': all_anns,
                   'all_users': all_users,
                   'invite_user_form': invite_user_form})


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
    all_annotations = Annotation.objects.filter(user=user)
    # Completed annotations
    completed_annotations = all_annotations.filter(decision__in=['True',
                                                                 'False'])
    completed_records = [a.record for a in completed_annotations]
    completed_events = [a.event for a in completed_annotations]
    # Uncertain / saved annotations
    uncertain_annotations = all_annotations.filter(decision='Uncertain')
    uncertain_records = [a.record for a in uncertain_annotations]
    uncertain_events = [a.event for a in uncertain_annotations]

    # Hold all of the annotation information
    completed_anns = {}
    uncertain_anns = {}
    incompleted_anns = {}

    # Get list where each element is a list of records from a project folder
    all_projects = base.ALL_PROJECTS
    # Get all user events
    user_events = {}
    for project in all_projects:
        user_events[project] = get_user_events(user, project)
    for ann in all_annotations:
        if ann.event not in user_events[ann.project]:
            user_events[ann.project].append(ann.event)
    # Get all user records
    user_records = {}
    for project in all_projects:
        events = user_events[project]
        user_records[project] = []
        for evt in events:
            rec = evt[:evt.find('_')]
            if rec not in user_records[project]:
                user_records[project].append(rec)
    for ann in all_annotations:
        if ann.record not in user_records[ann.project]:
            user_records[ann.project].append(ann.record)

    # Get the total number of annotations
    total_anns = len(all_annotations)

    # Display user events
    for project,record_list in user_records.items():
        for rec in sorted(record_list):
            temp_events = [e for e in user_events[project] if e[:e.find('_')] == rec]

            # Add annotations by event
            temp_completed_anns = []
            temp_uncertain_anns = []
            temp_incompleted_anns = []
            for evt in temp_events:
                if (rec in completed_records) and (evt in completed_events):
                    ann = completed_annotations[completed_events.index(evt)]
                    temp_completed_anns.append([ann.event,
                                                ann.decision,
                                                ann.comments,
                                                ann.decision_date])
                elif (rec in uncertain_records) and (evt in uncertain_events):
                    ann = uncertain_annotations[uncertain_events.index(evt)]
                    temp_uncertain_anns.append([ann.event,
                                                ann.decision,
                                                ann.comments,
                                                ann.decision_date])
                else:
                    temp_incompleted_anns.append([evt, '-', '-', '-'])

            # Get the completion stats for each record
            if temp_completed_anns != []:
                progress_stats = f'{len(temp_completed_anns)}/{len(completed_annotations)}'
                temp_completed_anns.insert(0, progress_stats)
                temp_completed_anns.insert(1, project)
                completed_anns[rec] = temp_completed_anns
            if temp_uncertain_anns != []:
                progress_stats = f'{len(temp_uncertain_anns)}/{len(uncertain_annotations)}'
                temp_uncertain_anns.insert(0, progress_stats)
                temp_uncertain_anns.insert(1, project)
                uncertain_anns[rec] = temp_uncertain_anns
            if temp_incompleted_anns != []:
                total_incompleted_anns = total_anns - \
                                        len(completed_annotations) - \
                                        len(uncertain_annotations)
                progress_stats = f'{len(temp_incompleted_anns)}/{total_incompleted_anns}'
                temp_incompleted_anns.insert(0, progress_stats)
                temp_incompleted_anns.insert(1, project)
                incompleted_anns[rec] = temp_incompleted_anns

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

            # Add events to user_assignments if not already present
            for project in available_projects:
                records_path = os.path.join(PROJECT_PATH, project, base.RECORDS_FILE)
                with open(records_path, 'r') as f:
                    record_list = f.read().splitlines()
                all_events = []
                for record in record_list:
                    event_path = os.path.join(PROJECT_PATH, project, record,
                                              base.RECORDS_FILE)
                    with open(event_path, 'r') as f:
                        all_events += f.read().splitlines()
                all_events = [e for e in all_events if '_' in e]
                csv_data = get_all_assignments(project)
                for event in all_events:
                    if event not in csv_data.keys():
                        csv_data[event] = []

                if num_events == 0:
                    update_assignments(csv_data, project)
                    break
                # Assign user events that have not been previously assigned to them
                finished_ann = Annotation.objects.filter(user=user, project=project)
                finished_event = [a.event for a in finished_ann]
                max_ann = 2

                for event, names_list in csv_data.items():
                    if event not in finished_event and \
                            user.username not in names_list and \
                            len(names_list) < max_ann and \
                            num_events > 0:
                        names_list.append(user.username)
                        num_events -= 1

                update_assignments(csv_data, project)

            return redirect('render_annotations')

    return render(request, 'waveforms/annotations.html',
                  {'user': user, 'all_anns_frac': all_anns_frac,
                   'categories': categories, 'completed_anns': completed_anns,
                   'uncertain_anns': uncertain_anns,
                   'incompleted_anns': incompleted_anns,
                   'finished_assignment': finished_assignment,
                   'remaining': total_anns-len(completed_annotations)})


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
            user = user,
            project = set_project,
            record = set_record,
            event = set_event
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
    seven_days = now - timedelta(days=7)

    # Get global leaderboard info
    glob_today = []
    glob_week = []
    glob_month = []
    glob_all = []
    glob_true = []
    glob_false = []
    for user in all_users:
        user_anns = Annotation.objects.filter(user=user).exclude(decision='Uncertain')
        num_today = 0
        num_week = 0
        num_month = 0
        num_all = 0
        num_true = 0
        num_false = 0
        for ann in user_anns:
            if ann.decision_date.day == now.day:
                num_today += 1
            if now >= ann.decision_date.date() >= seven_days:
                num_week += 1
            if ann.decision_date.month == now.month:
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

    return render(request, 'waveforms/leaderboard.html', {'user': current_user,
                                                          'glob_today': glob_today, 'glob_week': glob_week,
                                                          'glob_month': glob_month, 'glob_all': glob_all,
                                                          'glob_true': glob_true, 'glob_false': glob_false,
                                                          'user_today': user_today, 'user_week': user_week,
                                                          'user_month': user_month, 'user_all': user_all,
                                                          'user_true': user_true, 'user_false': user_false
                                                          })


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
