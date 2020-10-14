import os
import wfdb
import math
import datetime
import pandas as pd
import django.core.cache
from website.settings import base
from waveforms.models import Annotation
# Data analysis and visualization
import dash
import plotly.graph_objs as go
import dash_core_components as dcc
import dash_html_components as html
from django_plotly_dash import DjangoDash
from plotly.subplots import make_subplots


# Specify the record file locations
BASE_DIR = base.BASE_DIR
FILE_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))
FILE_LOCAL = os.path.join('record-files')
PROJECT_PATH = os.path.join(FILE_ROOT, FILE_LOCAL)
# Formatting settings
dropdown_width = "300px"

# Initialize the Dash App
app = DjangoDash(name='waveform_graph', id='target_id', assets_folder="assets")
# Specify the app layout
app.layout = html.Div([
    # The record dropdown
    html.Div([
        html.Label(['Select Record to Plot']),
        dcc.Dropdown(
            id = 'dropdown_rec',
            multi = False,
            clearable = False,
            searchable = True,
            placeholder = 'Please Select...',
            style = {"width": dropdown_width},
            persistence = True,
            persistence_type = 'session',
        ),
    ], style={'display': 'inline-block'}),
    # The event dropdown
    html.Div([
        html.Label(['Select Event to Plot']),
        dcc.Dropdown(
            id = 'dropdown_event',
            multi = False,
            clearable = False,
            searchable = True,
            placeholder = 'Please Select...',
            style = {"width": dropdown_width},
            persistence = True,
            persistence_type = 'session',
        ),
    ], style={'display': 'inline-block'}),
    # The plot itself
    html.Div([
        dcc.Graph(id = 'the_graph'),
    ]),
    # The event display
    html.Div([
        html.Div(id = 'event_text')
    ]),
    # Hidden div inside the app that stores the project record and event
    dcc.Input(id = 'target_id', type = 'hidden', value = ''),
    # The reviewer decision and comment section
    html.Label(['Enter decision here:']),
    dcc.Dropdown(
        id = 'reviewer_decision',
        options = [
            {'label': 'True (alarm is correct)', 'value': 'True'},
            {'label': 'False (alarm is incorrect)', 'value': 'False'},
            {'label': 'Reject (remove from database)', 'value': 'Reject'},
            {'label': 'Uncertain', 'value': 'Uncertain'}
        ],
        multi = False,
        clearable = False,
        searchable = False,
        placeholder = 'Please Select...',
        style = {"width": dropdown_width},
        persistence = False
    ),
    html.Label(['Enter comments here:']),
    html.Div(
        dcc.Textarea(id = 'reviewer_comments',
                     style = {
                         'width': '1000px',
                         'height': '100px'
                     })
    ),
    html.Button('Submit', id = 'submit_time'),
    html.Div(id = 'reviewer_display',
             children = 'Enter a value and press submit')
])


# The reviewer decision and comment section
@app.callback(
    dash.dependencies.Output('reviewer_display', 'children'),
    [dash.dependencies.Input('submit_time', 'n_clicks_timestamp')],
    [dash.dependencies.State('dropdown_rec', 'value'),
     dash.dependencies.State('dropdown_event', 'value'),
     dash.dependencies.State('reviewer_decision', 'value'),
     dash.dependencies.State('reviewer_comments', 'value')])
def reviewer_comment(submit_time, dropdown_rec, dropdown_event,
                     reviewer_decision, reviewer_comments):
    input_time = datetime.datetime.fromtimestamp(submit_time / 1000.0)
    # Save the annotation to the database
    annotation = Annotation(
        project = dropdown_rec,
        record = dropdown_event,
        decision = reviewer_decision,
        comments = reviewer_comments,
        decision_date = input_time
    )
    annotation.save()
    return 'The input value was {} at {} with comments "{}"'.format(reviewer_decision,
                                                         input_time,
                                                         reviewer_comments)


# Clear reviewer comments
@app.callback(
    dash.dependencies.Output('reviewer_comments', 'value'),
    [dash.dependencies.Input('dropdown_event', 'value')])
def clear_text(dropdown_event):
    return ''


# Dynamically update the record dropdown settings using the project 
# record and event
@app.callback(
    dash.dependencies.Output('dropdown_rec', 'options'),
    [dash.dependencies.Input('target_id', 'value')])
def get_records_options(target_id):
    # Get the record file
    records_path = os.path.join(PROJECT_PATH, 'RECORDS')
    with open(records_path, 'r') as f:
        all_records = f.read().splitlines()

    # Set the record options based on the current project
    options_rec = [{'label': rec, 'value': rec} for rec in all_records]

    return options_rec


# Dynamically update the signal dropdown settings using the record name, project 
# slug, and version
@app.callback(
    dash.dependencies.Output('dropdown_event', 'options'),
    [dash.dependencies.Input('dropdown_rec', 'value'),
     dash.dependencies.Input('target_id', 'value')])
def get_signal_options(dropdown_rec, target_id):
    # Get the header file
    header_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_rec)
    temp_rec = wfdb.rdheader(header_path).seg_name
    temp_rec = [s for s in temp_rec if s != (dropdown_rec+'_layout') and s != '~']

    # Set the options based on the annotated event times of the chosen record 
    options_rec = [{'label': t, 'value': t} for t in temp_rec]

    return options_rec


# Update the event text
@app.callback(
    dash.dependencies.Output('event_text', 'children'),
    [dash.dependencies.Input('dropdown_rec', 'value'),
     dash.dependencies.Input('dropdown_event', 'value')])
def update_text(dropdown_rec, dropdown_event):
    # Get the header file
    header_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_rec)
    temp_rec = wfdb.rdheader(header_path).seg_name
    temp_rec = [s for s in temp_rec if s != (dropdown_rec+'_layout') and s != '~']
    # Get the annotation information
    ann_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_rec)
    ann = wfdb.rdann(ann_path, 'cba')
    ann_event = ann.aux_note[temp_rec.index(dropdown_event)]

    return [
        html.Span('Event: {}'.format(ann_event), style={'fontSize': '36px'})
    ]


# Run the app using the chosen initial conditions
@app.callback(
    dash.dependencies.Output('the_graph', 'figure'),
    [dash.dependencies.Input('dropdown_rec', 'value'),
     dash.dependencies.Input('dropdown_event', 'value'),
     dash.dependencies.Input('target_id', 'value')])
def update_graph(dropdown_rec, dropdown_event, target_id):
    # Set some initial conditions
    record_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_event)
    record = wfdb.rdrecord(record_path)

    # Maybe down-sample signal if too slow?
    down_sample = 1
    # Determine the time of the event (seconds)
    # `300` if standard 10 minute segment, `dropdown_event` otherwise
    event_time = 300
    # How much signal should be displayed before and after event (seconds)
    time_range = 60
    time_start = record.fs * (event_time - time_range)
    time_stop = record.fs * (event_time + time_range)
    # Determine how much signal to display before and after event (seconds)
    window_size = 15
    # Grid and zero-line color
    # gridzero_color = 'rgb(255, 60, 60)'
    # ECG gridlines parameters
    # grid_delta_major = 0.2

    # Set the initial layout of the figure
    fig = make_subplots(
        rows = 4,
        cols = 1,
        shared_xaxes = True,
        vertical_spacing = 0
    )
    fig.update_layout({
        'height': 750,
        'grid': {
            'rows': record.n_sig,
            'columns': 1,
            'pattern': 'independent'
        },
        'showlegend': False,
        'hovermode': 'x'
    })

    # Name the axes to create the subplots
    for r in range(record.n_sig):
        x_string = 'x' + str(r+1)
        y_string = 'y' + str(r+1)
        # Generate the waveform x-values and y-values
        x_vals = [(i / record.fs) for i in range(record.sig_len)][time_start:time_stop:down_sample]
        y_vals = record.p_signal[:,r][time_start:time_stop:down_sample]
        # Set the initial display range of y-values based on values in
        # initial range of x-values
        index_start = record.fs * (event_time - window_size)
        index_stop = record.fs * (event_time + window_size)
        min_y_vals = min(record.p_signal[:,r][index_start:index_stop])
        max_y_vals = max(record.p_signal[:,r][index_start:index_stop])

        # Create the signal to plot
        fig.add_trace(go.Scatter({
            'x': x_vals,
            'y': y_vals,
            'xaxis': x_string,
            'yaxis': y_string,
            'type': 'scatter',
            'line': {
                'color': 'black',
                'width': 3
            },
            'name': record.sig_name[r]
        }), row = r+1, col = 1)
        # Display where the event is
        fig.add_shape({
            'type': 'line',
            'x0': event_time,
            'y0': min(y_vals) - 0.5 * (max(y_vals) - min(y_vals)),
            'x1': event_time,
            'y1': max(y_vals) + 0.5 * (max(y_vals) - min(y_vals)),
            'xref': x_string,
            'yref': y_string,
            'line': {
                'color': 'Red',
                'width': 3
            }
        })

        # Set the initial y-axis parameters
        fig.update_yaxes({
            'title': record.sig_name[r] + ' (' + record.units[r] + ')',
            'fixedrange': False,
            'showgrid': True,
            #'dtick': grid_delta_major,
            'showticklabels': True,
            #'gridcolor': gridzero_color,
            'zeroline': True,
            #'zerolinewidth': 1,
            #'zerolinecolor': gridzero_color,
            #'gridwidth': 1,
            'range': [min_y_vals, max_y_vals],
        }, row = r+1, col = 1)

        # Set the initial x-axis parameters
        if r == record.n_sig-1:
            fig.update_xaxes({
                'title': 'Time (s)',
                'showgrid': True,
                #'dtick': grid_delta_major,
                'showticklabels': True,
                #'gridcolor': gridzero_color,
                'zeroline': True,
                #'zerolinewidth': 1,
                #'zerolinecolor': gridzero_color,
                #'gridwidth': 1,
                'range': [event_time - window_size, event_time + window_size],
                'rangeslider': {
                    'visible': False
                }
            }, row = r+1, col = 1)

        else:
            fig.update_xaxes({
                #'title': 'Time (s)',
                'showgrid': True,
                #'dtick': grid_delta_major,
                'showticklabels': False,
                #'gridcolor': gridzero_color,
                'zeroline': True,
                #'zerolinewidth': 1,
                #'zerolinecolor': gridzero_color,
                #'gridwidth': 1,
                'range': [event_time - window_size, event_time + window_size],
                'rangeslider': {
                    'visible': False
                }
            }, row = r+1, col = 1)

    return (fig)
