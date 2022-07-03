import csv
import datetime
import os

import dash
import dash_core_components as dcc
import dash_html_components as html
from django_plotly_dash import DjangoDash
import numpy as np
import pytz
import wfdb

from waveforms.dash_apps.finished_apps.waveform_vis_tools import WaveformVizTools
from waveforms.models import Annotation, User
from website.middleware import get_current_user
from website.settings import base


# Specify the record file locations
BASE_DIR = base.BASE_DIR
FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
FILE_LOCAL = os.path.join('record-files')
PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)
ALL_PROJECTS = base.ALL_PROJECTS
# Formatting settings
sidebar_width = '100%'
event_fontsize = '100%'
comment_box_width = '90%'
comment_box_height = '30vh'
label_fontsize = '100%'
button_height = '10%'
submit_width = '49%'
arrow_width = '23%'
# Set the default configuration of the plot top buttons
plot_config = {
    'responsive': True,
    'displayModeBar': True,
    'modeBarButtonsToAdd': [
    ],
    'modeBarButtonsToRemove': [
        'hoverClosestCartesian',
        'hoverCompareCartesian',
        'toggleSpikelines',
        'pan2d',
        'zoom2d',
        'resetScale2d'
    ]
}


# Initialize the Dash App
app = DjangoDash(name='waveform_graph')
# Specify the app layout
app.layout = html.Div([
    dcc.Loading(id='loading-1', children=[
        # Area to submit annotations
        html.Div([
            # The project display
            html.Label(['Project:']),
            html.Div(
                id='dropdown_project',
                children=html.Span([''], style={'fontSize': event_fontsize})
            ),
            # The record display
            html.Label(['Record:']),
            html.Div(
                id='dropdown_record',
                children=html.Span([''], style={'fontSize': event_fontsize})
            ),
            # The event display
            html.Label(['Event:']),
            html.Div(
                id='dropdown_event',
                children=html.Span([''], style={'fontSize': event_fontsize})
            ),
            # The event display
            html.Label(['Event Type:']),
            html.Div(
                id='event_text',
                children=html.Span([''], style={'fontSize': event_fontsize})
            ),
            # The reviewer decision section
            html.Label(['Enter decision here:'],
                       style={'font-size': label_fontsize}),
            dcc.RadioItems(
                id='reviewer_decision',
                options=[
                    {'label': 'True (alarm is correct)', 'value': 'True'},
                    {'label': 'False (alarm is incorrect)', 'value': 'False'},
                    {'label': 'Uncertain', 'value': 'Uncertain'},
                    {'label': 'Reject (alarm is un-readable)', 'value': 'Reject'},
                    {'label': 'Save for Later', 'value': 'Save for Later'}
                ],
                labelStyle={'display': 'block'},
                style={'width': sidebar_width},
                persistence=False
            ),
            html.Br(),
            # The reviewer comment section
            html.Label(['Enter comments here:'],
                       style={'font-size': label_fontsize}),
            html.Div(
                dcc.Textarea(id='reviewer_comments',
                             style={
                                'width': comment_box_width,
                                'height': comment_box_height,
                                'font-size': label_fontsize
                             })
            ),
            # Submit annotation decision and comments
            html.Button('Submit',
                        id='submit_annotation',
                        style={'height': button_height,
                               'width': submit_width,
                               'font-size': 'large'}),
            # Select previous or next annotation
            html.Button('\u2190',
                        id='previous_annotation',
                        style={'height': button_height,
                               'width': arrow_width,
                               'font-size': 'large'}),
            html.Button('\u2192',
                        id='next_annotation',
                        style={'height': button_height,
                               'width': arrow_width,
                               'font-size': 'large'}),
        ], style={'display': 'inline-block', 'vertical-align': 'top',
                  'width': '20vw', 'margin-left': '10vw',
                  'padding-top': '2%'}),
        # The plot itself
        html.Div([
            dcc.Graph(
                id='the_graph',
                config=plot_config,
                style={'height': '70vh', 'width': '60vw'}
            ),
        ], style={'display': 'inline-block'})
    ], type='default'),
    # Hidden div inside the app that stores the desired project, record, and event
    dcc.Input(id='set_project', type='hidden', persistence=False, value=''),
    dcc.Input(id='set_record', type='hidden', persistence=False, value=''),
    dcc.Input(id='set_event', type='hidden', persistence=False, value=''),
    # Hidden div inside the app that stores the current project, record, and event
    dcc.Input(id='temp_project', type='hidden', persistence=False, value=''),
    dcc.Input(id='temp_record', type='hidden', persistence=False, value=''),
    dcc.Input(id='temp_event', type='hidden', persistence=False, value=''),
])


def get_practice_anns(ann):
    """
    Filter Annotation object to only include events in practice set.

    Parameters
    ----------
    ann : Annotation object
        Object to be filtered.

    Returns
    -------
    ann: Annotation object
        Filtered object.

    """
    events_per_proj = [list(events.keys()) for events in base.PRACTICE_SET.values()]
    events = []
    for i in events_per_proj:
        events += i
    return ann.filter(
        project__in=[key for key in base.PRACTICE_SET.keys()],
        event__in=events
    )


def get_all_records_events(project_folder):
    """
    Get all possible records and events.

    Parameters
    ----------
    project_folder : str
        The project used to retrieve the records and events.

    Returns
    -------
    N/A : list[str]
        List of all records.
    N/A : list[str]
        List of all events.

    """
    # Get records
    records_path = os.path.join(PROJECT_PATH, project_folder,
                                base.RECORDS_FILE)
    with open(records_path, 'r') as f:
        record_list = f.read().splitlines()
    # Get events
    event_list = []
    for record in record_list:
        event_path = os.path.join(PROJECT_PATH, project_folder, record,
                                  base.RECORDS_FILE)
        with open(event_path, 'r') as f:
            event_list += f.read().splitlines()
    event_list = [e for e in event_list if '_' in e]
    return record_list, event_list


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
    N/A: list[str]
        List of events assigned to the user.

    """
    # Find the files
    BASE_DIR = base.BASE_DIR
    FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
    FILE_LOCAL = os.path.join('record-files')
    PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)

    if user.is_admin and user.practice_status == 'ED':
        record_list, event_list = get_all_records_events(project_folder)
    elif user.practice_status != 'ED':
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


def get_user_records(user):
    """
    Get the records assigned to a user in the CSV file.

    Parameters
    ----------
    user : User
        The User whose records will be retrieved.

    Returns
    -------
    N/A: dict
        The records assigned to the user by project.

    """
    user_records = {}
    if user.is_admin and user.practice_status == 'ED':
        for project in ALL_PROJECTS:
            temp_records, _ = get_all_records_events(project)
            user_records[project] = temp_records
        return user_records
    if user.practice_status == 'ED':
        # Get all user annotations
        annotations = Annotation.objects.filter(
            user=user, is_adjudication=False
        )
        if user.practice_status != 'ED':
            annotations = get_practice_anns(annotations)
        # Get all user events
        user_events = {}
        for project in ALL_PROJECTS:
            user_events[project] = get_user_events(user, project)
        # Get all user records
        for project in ALL_PROJECTS:
            events = user_events[project]
            user_records[project] = []
            for evt in events:
                rec = evt[:evt.find('_')]
                if rec not in user_records[project]:
                    user_records[project].append(rec)
        for ann in annotations:
            if ann.record not in user_records[ann.project]:
                user_records[ann.project].append(ann.record)

    return user_records


def get_header_info(project, file_path):
    """
    Return all records/events in header from file path.

    Parameters
    ----------
    project : str
        Which project the record is in
    file_path : str
        The directory of the record file to be read.

    Returns
    -------
    file_contents : list[str]
        The stripped and cleaned lines of the record file. Essentially, all
        of the records to be read.

    """
    current_user = User.objects.get(username=get_current_user())
    records_path = os.path.join(PROJECT_PATH, project, file_path,
                                base.RECORDS_FILE)
    with open(records_path, 'r') as f:
        file_contents = f.read().splitlines()
    all_events = get_user_events(current_user, project)
    file_contents = [e for e in file_contents if '_' in e and e in all_events]
    return file_contents


@app.callback(
    [dash.dependencies.Output('dropdown_record', 'children'),
     dash.dependencies.Output('dropdown_event', 'children'),
     dash.dependencies.Output('dropdown_project', 'children'),
     dash.dependencies.Output('event_text', 'children'),
     dash.dependencies.Output('temp_project', 'value'),
     dash.dependencies.Output('temp_record', 'value'),
     dash.dependencies.Output('temp_event', 'value')],
    [dash.dependencies.Input('submit_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('previous_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('next_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('set_project', 'value'),
     dash.dependencies.Input('set_record', 'value'),
     dash.dependencies.Input('set_event', 'value')],
    [dash.dependencies.State('temp_project', 'value'),
     dash.dependencies.State('temp_record', 'value'),
     dash.dependencies.State('temp_event', 'value'),
     dash.dependencies.State('reviewer_decision', 'value'),
     dash.dependencies.State('reviewer_comments', 'value')])
def get_record_event_options(click_submit, click_previous, click_next,
                             set_project, set_record, set_event,
                             project_value, record_value, event_value,
                             decision_value, comments_value):
    """
    Dynamically update the labels and stored variables given the current
    record and event.

    Parameters
    ----------
    click_submit : int
        The timestamp if the submit button was clicked in ms from epoch.
    click_previous : int
        The timestamp if the previous button was clicked in ms from epoch.
    click_next : int
        The timestamp if the next button was clicked in ms from epoch.
    set_project : str
        The desired project.
    set_record : str
        The desired record.
    set_event : str
        The desired event.
    project_value : str
        The current project.
    record_value : str
        The current record.
    event_value : str
        The current event.
    decision_value : str
        The decision of the user.
    comments_value : str
        The comments of the user.

    Returns
    -------
    return_record : list[html.Span object]
        The current record in HTML form so it can be rendered on the page.
    return_event : list[html.Span object]
        The current event in HTML form so it can be rendered on the page.
    event_text : list[html.Span object]
        The current event in HTML form so it can be rendered on the page.
    dropdown_record : str
        The new selected record.
    dropdown_event : str
        The new selected event.

    """
    # Determine what triggered this function
    ctx = dash.callback_context
    # Prepare to return the record and event value for the user
    current_user = User.objects.get(username=get_current_user())
    # One project at a time
    if current_user.practice_status == 'ED':
        project = list(set(base.ALL_PROJECTS) - set(base.BLACKLIST))[0]
        user_annotations = Annotation.objects.filter(
            user=current_user, project=project, is_adjudication=False)
    else:
        project = [i for i in base.PRACTICE_SET.keys()][0]
        user_annotations = Annotation.objects.filter(
            user=current_user, project=project, is_adjudication=False)
        user_annotations = get_practice_anns(user_annotations)

    # Display "Save for Later" first
    user_annotations = sorted(
        user_annotations, key=lambda x: 0 if x.decision=='Save for Later' else 1
    )
    all_events = []
    # Handle initial load
    if not project_value:
        # Completed annotations
        completed_events = []
        for a in user_annotations:
            completed_events.append([a.project, a.event])
        # Every assigned event / future annotation
        proj_events = get_user_events(current_user, project)
        for event in proj_events:
            all_events.append([project, event])
        if all_events != []:
            # Get the earliest annotation
            if completed_events:
                ann_indices = [all_events.index(a) for a in completed_events]
                all_indices = sorted(list(set(np.arange(len(all_events))) - set(ann_indices))) + ann_indices
                current_event = all_indices[0]
            else:
                current_event = 0
            return_project = all_events[current_event][0]
            return_record = all_events[current_event][1].split('_')[0]
            return_event = all_events[current_event][1]
        else:
            # Display empty graph since no data
            return_project = 'N/A'
            return_record = 'N/A'
            return_event = 'N/A'
    else:
        completed_events = [a.event for a in user_annotations if a.project==project_value]
        if current_user.is_admin and current_user.practice_status == 'ED':
            _, all_events = get_all_records_events(project_value)
        else:
            all_events = get_user_events(current_user, project_value)
        # The indices of completed annotations
        ann_indices = [all_events.index(a) for a in completed_events]
        # The indices of incomplete annotations
        non_ann_indices = sorted(list(set(np.arange(len(all_events))) - set(ann_indices)))
        # Eventually `len(non_ann_indices) == 0` so "Save for Later" will
        # be first
        all_indices = non_ann_indices + ann_indices

    if ctx.triggered:
        # Determine what triggered the function
        click_id = ctx.triggered[0]['prop_id'].split('.')[0]
        # We already know the current project
        return_project = project_value
        # The location of event in the sorted event list
        event_idx = all_indices.index(all_events.index(event_value))
        # Going backward in the list
        if click_id == 'previous_annotation':
            return_record = all_events[all_indices[event_idx-1]].split('_')[0]
            return_event = all_events[all_indices[event_idx-1]]
        # Going forward in the list
        elif (click_id == 'next_annotation') or (click_id == 'submit_annotation'):
            try:
                return_record = all_events[all_indices[event_idx+1]].split('_')[0]
                return_event = all_events[all_indices[event_idx+1]]
            except IndexError:
                # End of list, go back to the beginning
                return_record = all_events[all_indices[0]].split('_')[0]
                return_event = all_events[all_indices[0]]

        # Update the annotations: only save the annotations if a decision is
        # made and the submit button was pressed
        if decision_value and (click_id == 'submit_annotation'):
            # Convert ms from epoch to datetime object (localize to the time
            # zone in the settings)
            submit_time = datetime.datetime.fromtimestamp(click_submit/1000.0)
            set_timezone = pytz.timezone(base.TIME_ZONE)
            submit_time = set_timezone.localize(submit_time)
            # Save the annotation to the database only if changes
            # were made or a new annotation
            try:
                res = Annotation.objects.get(
                    user=current_user, project=project_value,
                    record=record_value, event=event_value,
                    is_adjudication=False
                )
                current_annotation = [res.decision, res.comments]
                proposed_annotation = [decision_value, comments_value]
                # Only save annotation if something has changed
                if current_annotation != proposed_annotation:
                    annotation = Annotation(
                        user=current_user, project=project_value,
                        record=record_value, event=event_value,
                        decision=decision_value, comments=comments_value,
                        decision_date=submit_time, is_adjudication=False
                    )
                    annotation.update()
            except Annotation.DoesNotExist:
                # Create new annotation since none already exist
                annotation = Annotation(
                    user=current_user, project=project_value,
                    record=record_value, event=event_value,
                    decision=decision_value, comments=comments_value,
                    decision_date=submit_time, is_adjudication=False
                )
                annotation.update()
    else:
        # See if record and event was requested (never event without record)
        if set_record != '':
            return_project = set_project
            return_record = set_record
            return_event = set_event

    # Update the event text
    alarm_text = html.Span([''], style={'fontSize': event_fontsize})
    if ((return_record == 'N/A') or (return_event == 'N/A') or
        (return_project == 'N/A')):
        alarm_text = [
            html.Span(['N/A', html.Br(), html.Br()],
                      style={'fontSize': event_fontsize})
        ]
    else:
        # Get the annotation information
        ann_path = os.path.join(PROJECT_PATH, return_project,
                                return_record, return_event)
        ann = wfdb.rdann(ann_path, 'alm')
        ann_event = ann.aux_note[0]
        # Update the annotation event text
        alarm_text = [
            html.Span(['{}'.format(ann_event), html.Br(), html.Br()],
                      style={'fontSize': event_fontsize})
        ]

    # Update the annotation current project text
    project_text = [
        html.Span(['{}'.format(return_project)],
                  style={'fontSize': event_fontsize})
    ]
    # Update the annotation current record text
    record_text = [
        html.Span(['{}'.format(return_record)],
                  style={'fontSize': event_fontsize})
    ]
    # Update the annotation current event text
    event_text = [
        html.Span(['{}'.format(return_event)],
                  style={'fontSize': event_fontsize})
    ]

    return (record_text, event_text, project_text, alarm_text,
            return_project, return_record, return_event)


@app.callback(
    [dash.dependencies.Output('the_graph', 'figure'),
     dash.dependencies.Output('reviewer_decision', 'value'),
     dash.dependencies.Output('reviewer_comments', 'value')],
    [dash.dependencies.Input('dropdown_event', 'children')],
    [dash.dependencies.State('dropdown_record', 'children'),
     dash.dependencies.State('dropdown_project', 'children')])
def update_graph(dropdown_event, dropdown_record, dropdown_project):
    """
    Run the app and render the waveforms using the chosen initial conditions.

    Parameters
    ----------
    dropdown_event : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current record.
    dropdown_record : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current event.
    dropdown_project : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current project.

    Returns
    -------
    N/A : plotly.subplots
        The final figure.
    N/A : str
        The cleared decision of the user.
    N/A : str
        The cleared comments of the user.

    """
    # Import the waveform tools for the current user
    current_user = get_current_user()
    wvt = WaveformVizTools(current_user)
    # Create the figure
    dropdown_record = wvt.get_dropdown(dropdown_record)
    dropdown_event = wvt.get_dropdown(dropdown_event)
    dropdown_project = wvt.get_dropdown(dropdown_project)
    # Blank figure if empty
    if ((dropdown_record == 'N/A') or (dropdown_event == 'N/A') or
       (dropdown_project == 'N/A')):
        fig = wvt.create_blank_figure()
        return (fig), None, ''
    # Final figure
    fig = wvt.create_final_figure(
        dropdown_project, dropdown_record, dropdown_event
    )

    # Clear the reviewer decision and comments if none has been created or load
    # them otherwise when loading a new record and event.
    if (dropdown_event != '') and (dropdown_event is not None) and (current_user != ''):
        # Get the decision
        user = User.objects.get(username=current_user)
        try:
            res = Annotation.objects.get(
                user=user, project=dropdown_project, record=dropdown_record,
                event=dropdown_event, is_adjudication=False
            )
            return_decision = res.decision
            return_comments = res.comments
        except Annotation.DoesNotExist:
            return_decision = None
            return_comments = ''
    else:
        return_decision = None
        return_comments = ''

    return (fig), return_decision, return_comments
