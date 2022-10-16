from collections import Counter
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
annotations_width = '100%'
sidebar_width = '14.58%'
event_fontsize = '100%'
comment_box_width = '90%'
comment_box_height = '15vh'
label_fontsize = '100%'
button_height = '10%'
button_width = '50%'
# Set the default configuration of the plot top buttons
plot_config = {
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
app = DjangoDash(name='waveform_graph_adjudicate')
# Specify the app layout
app.layout = html.Div([
    dcc.Loading(id='loading-1', children=[
        # Previously annotated values
        html.Div(
            id='annotation_table',
            children=html.Table(
                # Header
                [
                    html.Tr([
                        html.Th(col) for col in ['user','decision','comments','decision_date']
                    ], style={'text-align': 'left'})
                ] +
                # Body
                [
                    html.Tr([
                        html.Td('-') for col in ['user','decision','comments','decision_date']
                    ], style={'text-align': 'left'}) for _ in range(2)
                ],
                style={'width': '100%'}
            ),
            style={'display': 'block', 'width': annotations_width}
        ),
        html.Hr(),
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
            # Submit annotation decision and comments
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
            html.Br(),
            # For warning the user of their decision
            html.Div(id='output-provider'),
            dcc.ConfirmDialogProvider(
                children=html.Button(
                        'True',
                        style={'height': button_height,
                               'width': button_width,
                               'font-size': 'large'}),
                id='adjudication_true',
                message='You selected True... Are you sure you want to continue?'
            ),
            html.Br(),
            dcc.ConfirmDialogProvider(
                children=html.Button(
                        'False',
                        style={'height': button_height,
                               'width': button_width,
                               'font-size': 'large'}),
                id='adjudication_false',
                message='You selected False... Are you sure you want to continue?'
            ),
            html.Br(),
            dcc.ConfirmDialogProvider(
                children=html.Button(
                        'Uncertain',
                        style={'height': button_height,
                               'width': button_width,
                               'font-size': 'large'}),
                id='adjudication_uncertain',
                message='You selected Uncertain... Are you sure you want to continue?'
            ),
            html.Br(),
            dcc.ConfirmDialogProvider(
                children=html.Button(
                        'Reject',
                        style={'height': button_height,
                               'width': button_width,
                               'font-size': 'large'}),
                id='adjudication_reject',
                message='You selected Reject... Are you sure you want to continue?'
            ),
            html.Br(),
            html.Button('\u2192',
                        id='next_annotation',
                        style={'height': button_height,
                               'width': button_width,
                               'font-size': 'large'}),
        ], style={'display': 'inline-block', 'vertical-align': 'top',
                  'width': '20hw', 'margin-left': '10vw',
                  'padding-top': '3%'}),
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


def get_current_conflicting_annotation(project='', record='', event=''):
    """
    Get the current conflicting annotation which is needed to be adjudicated.

    PARAMETERS
    ----------
    project : str, optional
        The desired project.
    record : str, optional
        The desired record.
    event : str, optional
        The desired event.

    RETURNS
    -------
    N/A : tuple
        A list of the annotations which are conflicting in the form of:
            (project, record, event)

    """
    # Get info of all non-adjudicated annotations assuming non-unique event
    # names
    non_adjudicated_anns = Annotation.objects.filter(is_adjudication=False)
    all_info = [tuple(ann.values()) for ann in non_adjudicated_anns.values('project','record','event')]
    unique_anns = Counter(all_info).keys()
    ann_counts = Counter(all_info).values()
    # Get completed annotations (should be two but I guess could be more if
    # glitch or old data)
    completed_anns = [c[0] for c in list(zip(unique_anns,ann_counts)) if c[1]>=2]

    # Sort by `decision_date` with older conflicting annotations appearing
    # first to predictable traverse the remaining annotations.
    sorted_anns = []
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
            # Make sure there are conflicting decisions and no adjudications
            # already
            if is_conflicting:
                current_ann = non_adjudicated_anns.filter(
                    project=c[0], record=c[1], event=c[2]
                )
                # Get the most recent annotation (i.e. time of completion)
                current_ann = sorted(current_ann, key=lambda x: x.decision_date)[-1]
                sorted_anns.append(c + (current_ann.decision_date,))
    sorted_anns = sorted(sorted_anns, key=lambda x: x[-1].timestamp())

    # The oldest conflicting annotation (project, record, event)
    if sorted_anns:
        if project and record and event:
            # Get the index of the current annotation
            try:
                current_index = [a[:-1] for a in sorted_anns].index((project,record,event)) + 1
            except ValueError:
                # Annotation was just adjudicated, return to previous location
                current_annotations = Annotation.objects.filter(
                    project=project, record=record, event=event,
                    is_adjudication=False
                )
                current_timestamp = sorted(
                    current_annotations, key=lambda x: x.decision_date
                )[-1].decision_date
                current_index = np.searchsorted(
                    [a[-1] for a in sorted_anns[::-1]], current_timestamp,
                    side='left'
                ) - 1
                if (current_index < 0) or (current_index >= len(sorted_anns)):
                    return sorted_anns[0][:-1]
                else:
                    return sorted_anns[current_index][:-1]
            # Return the next one unless at the end of the list
            if current_index >= len(sorted_anns):
                return sorted_anns[0][:-1]
            else:
                return sorted_anns[current_index][:-1]
        else:
            return sorted_anns[0][:-1]
    else:
        return ('N/A', 'N/A', 'N/A')


@app.callback(
    [dash.dependencies.Output('dropdown_project', 'children'),
     dash.dependencies.Output('dropdown_record', 'children'),
     dash.dependencies.Output('dropdown_event', 'children'),
     dash.dependencies.Output('event_text', 'children'),
     dash.dependencies.Output('temp_project', 'value'),
     dash.dependencies.Output('temp_record', 'value'),
     dash.dependencies.Output('temp_event', 'value')],
    [dash.dependencies.Input('adjudication_true', 'submit_n_clicks'),
     dash.dependencies.Input('adjudication_false', 'submit_n_clicks'),
     dash.dependencies.Input('adjudication_uncertain', 'submit_n_clicks'),
     dash.dependencies.Input('adjudication_reject', 'submit_n_clicks'),
     dash.dependencies.Input('next_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('set_project', 'value'),
     dash.dependencies.Input('set_record', 'value'),
     dash.dependencies.Input('set_event', 'value')],
    [dash.dependencies.State('temp_project', 'value'),
     dash.dependencies.State('temp_record', 'value'),
     dash.dependencies.State('temp_event', 'value'),
     dash.dependencies.State('reviewer_comments', 'value')])
def get_record_event_options(submit_true, submit_false, submit_uncertain,
                             submit_reject, click_next, set_project,
                             set_record, set_event, project_value,
                             record_value, event_value, comments_value):
    """
    Dynamically update the record given the current record and event.

    Parameters
    ----------
    submit_true : int
        The number of times the submit true button was clicked.
    submit_false : int
        The number of times the submit false button was clicked.
    submit_uncertain : int
        The number of times the submit uncertain button was clicked.
    submit_reject : int
        The number of times the submit reject button was clicked.
    set_project : str
        The desired project.
    set_record : str
        The desired record.
    set_event : str
        The desired event.
    decision_value : str
        The decision of the user.
    comment_value : str
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

    """
    # Determine what triggered this function
    ctx = dash.callback_context
    # Prepare to return the record and event value for the user
    current_user = User.objects.get(username=get_current_user())

    # Handle initial load
    if not project_value:
        # Display the first conflicting event if none specified
        return_project, return_record, return_event = get_current_conflicting_annotation()

    # If something was triggered (submit, request, etc.)
    if ctx.triggered:
        # Determine what triggered the function
        click_id = ctx.triggered[0]['prop_id'].split('.')[0]
        # Submit the adjudication and reset
        adjudication_ids = ['adjudication_true', 'adjudication_false',
                            'adjudication_uncertain', 'adjudication_reject']
        if click_id in adjudication_ids:
            # Get the current time and localize to the time zone in the
            # settings
            submit_time = datetime.datetime.now(
                pytz.timezone(base.TIME_ZONE))
            # Convert the decision value to a recognized format
            decision_value = click_id.split('_')[1].capitalize()
            # Save the annotation to the database only if changes
            # were made or a new annotation
            try:
                res = Annotation.objects.get(
                    user=current_user, project=project_value,
                    record=record_value, event=event_value,
                    is_adjudication=True
                )
                current_annotation = [res.decision, res.comments]
                proposed_annotation = [decision_value, comments_value]
                # Only save annotation if something has changed
                if current_annotation != proposed_annotation:
                    # Delete the old one
                    res.delete()
                    # Save the new one
                    annotation = Annotation(
                        user=current_user, project=project_value,
                        record=record_value, event=event_value,
                        decision=decision_value, comments=comments_value,
                        decision_date=submit_time, is_adjudication=True
                    )
                    annotation.save()
            except Annotation.DoesNotExist:
                # Create new annotation since none already exist
                annotation = Annotation(
                    user=current_user, project=project_value,
                    record=record_value, event=event_value,
                    decision=decision_value, comments=comments_value,
                    decision_date=submit_time, is_adjudication=True
                )
                annotation.save()
            # We already know the current project, record, and event
            return_project, return_record, return_event = get_current_conflicting_annotation(
                project=project_value, record=record_value, event=event_value
            )
        elif click_id == 'next_annotation':
            # We already know the current project, record, and event
            return_project, return_record, return_event = get_current_conflicting_annotation(
                project=project_value, record=record_value, event=event_value
            )
    else:
        # See if record and event was requested (never event without record)
        if set_record != '':
            return_project = set_project
            return_record = set_record
            return_event = set_event

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

    # Update the event text
    alarm_text = html.Span([''], style={'fontSize': event_fontsize})
    if return_record and return_event and return_project:
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

    return (project_text, record_text, event_text, alarm_text,
            return_project, return_record, return_event)


@app.callback(
    [dash.dependencies.Output('the_graph', 'figure'),
     dash.dependencies.Output('annotation_table', 'children'),
     dash.dependencies.Output('reviewer_comments', 'value')],
    [dash.dependencies.Input('dropdown_project', 'children'),
     dash.dependencies.Input('dropdown_record', 'children'),
     dash.dependencies.Input('dropdown_event', 'children')])
def update_graph(dropdown_project, dropdown_record, dropdown_event):
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
    N/A : html.Table
        The table of previous annotations for the current adjudication.

    """
    # Import the waveform tools for the current user
    current_user = get_current_user()
    wvt = WaveformVizTools(current_user)
    # Update the adjudication information
    if not dropdown_project and not dropdown_record and not dropdown_event:
        dropdown_project, dropdown_record, dropdown_event = get_current_conflicting_annotation()
    else:
        dropdown_project = dropdown_project[0]['props']['children'][0]
        dropdown_record = dropdown_record[0]['props']['children'][0]
        dropdown_event = dropdown_event[0]['props']['children'][0]
    # Annotation table
    return_table = [
        html.Table(
            # Header
            [
                html.Tr([
                    html.Th(col) for col in ['user' , 'decision' , 'comments' , 'decision_date']
                ], style={'text-align': 'left'})
            ] +
            # Body
            [
                html.Tr([
                    html.Td('-') for _ in ['user' , 'decision' , 'comments' , 'decision_date']
                ], style={'text-align': 'left'}) for _ in range(2)
            ],
            style={'width': '100%'}
        )]
    # Blank figure if empty
    if ((dropdown_record == 'N/A') or (dropdown_event == 'N/A') or
       (dropdown_project == 'N/A')):
        fig = wvt.create_blank_figure()
        return (fig), return_table, ''
    # Figure
    fig = wvt.create_final_figure(
        dropdown_project, dropdown_record, dropdown_event
    )

    # Annotation table
    conflict_ann_dict = Annotation.objects.filter(
        project=dropdown_project, record=dropdown_record, event=dropdown_event
    ).values(
        *['user__username', 'decision', 'comments', 'decision_date']
    )
    for a in conflict_ann_dict:
        a['decision_date'] = a['decision_date'].astimezone(
            pytz.timezone(base.TIME_ZONE)).strftime('%B %d, %Y %H:%M:%S')
        if not a['comments']:
            a['comments'] = '-'
    return_table = [
        html.Table(
            # Header
            [
                html.Tr([
                    html.Th(col) for col in ['user__username', 'decision', 'comments', 'decision_date']
                ], style={'text-align': 'left'})
            ] +
            # Body
            [
                html.Tr([
                    html.Td(cad[col]) for col in ['user__username', 'decision', 'comments', 'decision_date']
                ], style={'text-align': 'left'}) for cad in conflict_ann_dict
            ],
            style={'width': '100%'}
        )]

    return (fig), return_table, ''
