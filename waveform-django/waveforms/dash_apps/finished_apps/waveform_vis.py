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
from waveforms.models import Annotation, User, WaveformEvent
from website.middleware import get_current_user
from website.settings import base
from django.core import cache

from pathlib import Path
from itertools import chain

PROJECT_PATH = Path(base.HEAD_DIR)/'record-files'

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
    dcc.Input(id='set_pageid', type='hidden', persistence=False, value=''),
    # Hidden div inside the app that stores the current project, record, and event
    dcc.Input(id='temp_project', type='hidden', persistence=False, value=''),
    dcc.Input(id='temp_record', type='hidden', persistence=False, value=''),
    dcc.Input(id='temp_event', type='hidden', persistence=False, value=''),
    dcc.Input(id='temp_pageid', type='hidden', persistence=False, value=''),

])


@app.callback(
    [dash.dependencies.Output('dropdown_project', 'children'),
     dash.dependencies.Output('dropdown_record', 'children'),
     dash.dependencies.Output('dropdown_event', 'children'),
     dash.dependencies.Output('event_text', 'children'),
     dash.dependencies.Output('temp_project', 'value'),
     dash.dependencies.Output('temp_record', 'value'),
     dash.dependencies.Output('temp_event', 'value'),
     dash.dependencies.Output('temp_pageid', 'value')],
    [dash.dependencies.Input('submit_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('previous_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('next_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('set_project', 'value'),
     dash.dependencies.Input('set_record', 'value'),
     dash.dependencies.Input('set_event', 'value'),
     dash.dependencies.Input('set_pageid', 'value')],
    [dash.dependencies.State('temp_project', 'value'),
     dash.dependencies.State('temp_record', 'value'),
     dash.dependencies.State('temp_event', 'value'),
     dash.dependencies.State('temp_pageid', 'value'),
     dash.dependencies.State('reviewer_decision', 'value'),
     dash.dependencies.State('reviewer_comments', 'value')])
def get_record_event_options(click_submit, click_previous, click_next,
                             set_project, set_record, set_event, set_pageid,
                             project_value, record_value, event_value, pageid_value,
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
    return_project : list[html.Span object]
        The current project in HTML form so it can be rendered on the page.
    return_record : list[html.Span object]
        The current record in HTML form so it can be rendered on the page.
    return_event : list[html.Span object]
        The current event in HTML form so it can be rendered on the page.
    event_text : list[html.Span object]
        The current event in HTML form so it can be rendered on the page.
    dropdown_project : str
        The new selected project.
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
    user_saved = current_user.get_waveforms('saved')
    user_unannotated = current_user.get_waveforms('unannotated')
    user_annotations = current_user.get_waveforms('annotated')

    all_waveforms = list(chain(user_saved, user_unannotated, user_annotations))

    print(f"\n\n set project: {set_project}\n set_record: {set_record}\n set_event: {set_event}\n set_pageid: {set_pageid}\n")

    if not set_project or not set_record or not set_event:
        pass

    if ctx.triggered:
        # Determine what triggered the function
        click_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        print(f"\n\nCLICK ID: {click_id}")

        # We already know the current project
        return_project = project_value

        # Going backward in the list
        if click_id == 'previous_annotation':
            return_record = 'v101l'
            return_event = 'v101l_1m'
            return_pageid = 0
        # Going forward in the list
        elif (click_id == 'next_annotation') or (click_id == 'submit_annotation'):
            try:
                return_record = 'v101l'
                return_event = 'v101l_1m'
                return_pageid = 0

            except IndexError:
                # End of list, go back to the beginning
                return_record = 'v101l'
                return_event = 'v101l_1m'
                return_pageid = 0

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
            waveform = WaveformEvent.objects.get(project=project_value, record=record_value, event=event_value)
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
                        decision_date=submit_time, is_adjudication=False,
                        waveform=waveform
                    )
                    annotation.update()
            except Annotation.DoesNotExist:
                # Create new annotation since none already exist
                annotation = Annotation(
                    user=current_user, project=project_value,
                    record=record_value, event=event_value,
                    decision=decision_value, comments=comments_value,
                    decision_date=submit_time, is_adjudication=False,
                    waveform=waveform
                )
                annotation.update()
    else:
        return_project = set_project
        return_record = set_record
        return_event = set_event
        return_pageid = set_pageid

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
        ann_path = str(PROJECT_PATH / return_project / return_record / return_event)
        ann = wfdb.rdann(ann_path, 'alm')
        ann_event = ann.aux_note[0]
        # Update the annotation event text
        alarm_text = [
            html.Span([f'{ann_event}', html.Br(), html.Br()],
                      style={'fontSize': event_fontsize})
        ]

    # Update the annotation current project text
    project_text = [
        html.Span([f'{return_project}'],
                  style={'fontSize': event_fontsize})
    ]
    # Update the annotation current record text
    record_text = [
        html.Span([f'{return_record}'],
                  style={'fontSize': event_fontsize})
    ]
    # Update the annotation current event text
    event_text = [
        html.Span([f'{return_event}'],
                  style={'fontSize': event_fontsize})
    ]

    print(f"\n\n project_value: {project_value}\n record_value: {record_value}\n event_value: {event_value}\n pageid_value: {pageid_value}\n")
    return (project_text, record_text, event_text, alarm_text,
            return_project, return_record, return_event, return_pageid)


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
