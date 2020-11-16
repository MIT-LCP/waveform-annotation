import os
import wfdb
import math
import datetime
import numpy as np
import pandas as pd
import django.core.cache
from website.middleware import get_current_user
from website.settings import base
from waveforms.models import Annotation
# API query
from schema import schema
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
dropdown_width = '200px'
event_fontsize = '36px'

# Initialize the Dash App
app = DjangoDash(name='waveform_graph', id='target_id', assets_folder='assets')
# Specify the app layout
app.layout = html.Div([
    # Area to submit annotations
    html.Div([
        # The record dropdown
        html.Div([
            html.Label(['Select Record to Plot']),
            dcc.Dropdown(
                id = 'dropdown_rec',
                multi = False,
                clearable = False,
                searchable = True,
                persistence = False,
                placeholder = 'Please Select...',
                style = {'width': dropdown_width},
            )
        ], style = {'display': 'inline-block'}),
        # The event dropdown
        html.Div([
            html.Label(['Select Event to Plot']),
            dcc.Dropdown(
                id = 'dropdown_event',
                multi = False,
                clearable = False,
                searchable = True,
                persistence = False,
                placeholder = 'Please Select...',
                style = {'width': dropdown_width},
            )
        ]),
        # The event display
        html.Div(
            id = 'event_text',
            children = html.Span([html.Br(), html.Br(), ''], style={'fontSize': event_fontsize})
        ),
        # The reviewer decision section
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
            style = {'width': dropdown_width},
            persistence = False
        ),
        # The reviewer comment section
        html.Label(['Enter comments here:']),
        html.Div(
            dcc.Textarea(id = 'reviewer_comments',
                        style = {
                            'width': dropdown_width,
                            'height': '300px'
                        })
        ),
        # Select previous or next annotation
        html.Button('Previous Annotation', id = 'previous_annotation'),
        html.Button('Next Annotation', id = 'next_annotation'),
    ], style = {'display': 'inline-block', 'vertical-align': '125px'}),
    # The plot itself
    html.Div([
        dcc.Graph(id = 'the_graph'),
    ], style = {'display': 'inline-block'}),
    # Hidden div inside the app that stores the project user, record, and event
    dcc.Input(id = 'set_record', type = 'hidden', value = ''),
    dcc.Input(id = 'set_event', type = 'hidden', value = ''),
])


# Clear/preset reviewer decision and comments
@app.callback(
    [dash.dependencies.Output('reviewer_decision', 'value'),
     dash.dependencies.Output('reviewer_comments', 'value')],
    [dash.dependencies.Input('set_event', 'value')])
def clear_text(set_event):
    current_user = get_current_user()
    if (set_event != '') and (set_event != None) and (current_user != ''):
        query = """
            {{
                all_annotations(user:"{}", event:"{}"){{
                    edges{{
                        node{{
                            decision
                        }}
                    }}
                }}
            }}
        """.format(current_user, set_event)
        res = schema.execute(query)
        if res.data['all_annotations']['edges'] == []:
            reviewer_decision = None
        else:
            reviewer_decision = res.data['all_annotations']['edges'][0]['node']['decision']
        query = """
            {{
                all_annotations(user:"{}", event:"{}"){{
                    edges{{
                        node{{
                            comments
                        }}
                    }}
                }}
            }}
        """.format(current_user, set_event)
        res = schema.execute(query)
        if res.data['all_annotations']['edges'] == []:
            reviewer_comments = ''
        else:
            reviewer_comments = res.data['all_annotations']['edges'][0]['node']['comments']

        return reviewer_decision, reviewer_comments

    else:
        return None, ''


# Dynamically update the record dropdown settings using the project 
# record and event
@app.callback(
    [dash.dependencies.Output('dropdown_rec', 'options'),
     dash.dependencies.Output('dropdown_rec', 'value')],
    [dash.dependencies.Input('previous_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('next_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('set_record', 'value')],
    [dash.dependencies.State('dropdown_event', 'options'),
     dash.dependencies.State('set_event', 'value'),
     dash.dependencies.State('reviewer_decision', 'value'),
     dash.dependencies.State('reviewer_comments', 'value')])
def get_records_options(click_previous, click_next, record_value, event_options,
                        event_value, decision_value, comments_value):
    # Get the record file
    records_path = os.path.join(PROJECT_PATH, 'RECORDS')
    with open(records_path, 'r') as f:
        all_records = f.read().splitlines()

    # Set the record options based on the current project
    options_rec = [{'label': rec, 'value': rec} for rec in all_records]

    # Set the value if provided
    return_record = record_value
    ctx = dash.callback_context
    if record_value != '':
        # Determine if called from another event or just loaded
        if len(ctx.triggered) > 0:
            if ctx.triggered[0]['prop_id'].split('.')[0] == 'previous_annotation':
                event_options = [e['value'] for e in event_options]
                if event_options.index(event_value) > 0:
                    # Event list not ended, keep record value the same
                    return_record = record_value
                else:
                    idx = all_records.index(record_value)
                    if idx == 0:
                        # Reached the end of the list, go back to the beginning
                        return_record = all_records[0]
                    else:
                        # Increment the record if not the end of the list
                        # TODO: Increment to the next non-annotated waveform instead?
                        return_record = all_records[idx-1]
            elif ctx.triggered[0]['prop_id'].split('.')[0] == 'next_annotation':
                event_options = [e['value'] for e in event_options]
                if event_options.index(event_value) < (len(event_options) - 1):
                    # Event list not ended, keep record value the same
                    return_record = record_value
                else:
                    idx = all_records.index(record_value)
                    if idx == (len(all_records) - 1):
                        # Reached the end of the list, go back to the beginning
                        return_record = all_records[0]
                    else:
                        # Increment the record if not the end of the list
                        # TODO: Increment to the next non-annotated waveform instead?
                        return_record = all_records[idx+1]
        else:
            # Requested record
            return_record = record_value
    else:
        if click_previous or click_next:
            # Determine which button was clicked
            if ctx.triggered[0]['prop_id'].split('.')[0] == 'previous_annotation':
                click_time = click_previous
            else:
                click_time = click_next

            time_now = datetime.datetime.now()
            # Convert ms from epoch to datetime object
            click_time = datetime.datetime.fromtimestamp(click_time / 1000.0)
            # Consider next annotation desired if button was pressed in the
            # last 1 second... change this?
            # TODO: make this better
            if (time_now - click_time).total_seconds() < 1:
                event_options = [e['value'] for e in event_options]
                if ctx.triggered[0]['prop_id'].split('.')[0] == 'previous_annotation':
                    if event_options.index(event_value) > 0:
                        # Event list not ended, keep record value the same
                        return_record = record_value
                    else:
                        idx = all_records.index(record_value)
                        if idx == 0:
                            # At the beginning of the list, go to the end
                            return_record = all_records[-1]
                        else:
                            # Decrement the record if not the beginning of the list
                            # TODO: Decrement to the next non-annotated waveform instead?
                            return_record = all_records[idx-1]
                else:
                    if event_options.index(event_value) < (len(event_options) - 1):
                        # Event list not ended, keep record value the same
                        return_record = record_value
                    else:
                        idx = all_records.index(record_value)
                        if idx == (len(all_records) - 1):
                            # Reached the end of the list, go back to the beginning
                            return_record = all_records[0]
                        else:
                            # Increment the record if not the end of the list
                            # TODO: Increment to the next non-annotated waveform instead?
                            return_record = all_records[idx+1]
            else:
                # Should theoretically never happen but here just in case
                return_record = record_value
        else:
            # Keep blank if loading main page (no presets)
            return_record = None

    # Update the annotations
    if len(ctx.triggered) > 0:
        if ((ctx.triggered[0]['prop_id'].split('.')[0] == 'previous_annotation') or
                (ctx.triggered[0]['prop_id'].split('.')[0] == 'next_annotation')):
            # Only save the annotations if a decision is made
            if decision_value:
                # Convert ms from epoch to datetime object
                if (ctx.triggered[0]['prop_id'].split('.')[0] == 'previous_annotation'):
                    submit_time = datetime.datetime.fromtimestamp(click_previous / 1000.0)
                elif (ctx.triggered[0]['prop_id'].split('.')[0] == 'next_annotation'):
                    submit_time = datetime.datetime.fromtimestamp(click_next / 1000.0)
                # Save the annotation to the database only if changes
                # were made or a new annotation
                current_user = get_current_user()
                query = """
                    {{
                        all_annotations(user:"{}", event:"{}"){{
                            edges{{
                                node{{
                                    record,
                                    event,
                                    decision,
                                    comments,
                                    decision_date
                                }}
                            }}
                        }}
                    }}
                """.format(current_user, event_value)
                res = schema.execute(query)
                if res.data['all_annotations']['edges'] != []:
                    current_annotation = list(res.data['all_annotations']['edges'][0]['node'].values())
                    proposed_annotation = [record_value, event_value,
                                           decision_value, comments_value]
                    # Only save annotation if something has changed
                    if current_annotation[:4] != proposed_annotation:
                        annotation = Annotation(
                            user = current_user,
                            record = record_value,
                            event = event_value,
                            decision = decision_value,
                            comments = comments_value,
                            decision_date = submit_time
                        )
                        annotation.update()
                else:
                    # Create new annotation since none already exist
                    annotation = Annotation(
                        user = current_user,
                        record = record_value,
                        event = event_value,
                        decision = decision_value,
                        comments = comments_value,
                        decision_date = submit_time
                    )
                    annotation.update()

    return options_rec, return_record


# Dynamically update the signal dropdown settings using the record name, project 
# slug, and version
@app.callback(
    [dash.dependencies.Output('dropdown_event', 'options'),
     dash.dependencies.Output('dropdown_event', 'value')],
    [dash.dependencies.Input('dropdown_rec', 'value')],
    [dash.dependencies.State('set_record', 'value'),
     dash.dependencies.State('set_event', 'value'),
     dash.dependencies.State('previous_annotation', 'n_clicks_timestamp'),
     dash.dependencies.State('next_annotation', 'n_clicks_timestamp')])
def get_event_options(dropdown_rec, set_record, set_event, click_previous, click_next):
    # Get the header file
    options_event = []
    if dropdown_rec:
        # Extract all the events
        header_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_rec)
        temp_event = wfdb.rdheader(header_path).seg_name
        temp_event = [s for s in temp_event if s != (dropdown_rec+'_layout') and s != '~']
        # Set the options based on the annotated event times of the chosen record
        options_event = [{'label': t, 'value': t} for t in temp_event]

    # Set the value if provided, change if requested
    return_event = None
    if set_event != '' and set_event:
        idx = temp_event.index(set_event)
        time_now = datetime.datetime.now()
        # Convert ms from epoch to datetime object
        if click_previous:
            click_previous = datetime.datetime.fromtimestamp(click_previous / 1000.0)
        if click_next:
            click_next = datetime.datetime.fromtimestamp(click_next / 1000.0)
        # Consider next annotation desired if button was pressed in the
        # last 1 second... change this?
        # TODO: make this better
        if click_previous and click_next:
            if (click_previous > click_next):
                if (time_now - click_previous).total_seconds() < 1:
                    if idx == 0:
                        # At the beginning of the list, go to the end
                        return_event = temp_event[-1]
                    else:
                        # Decrement the record if not the beginning of the list
                        # TODO: Decrement to the next non-annotated waveform instead?
                        return_event = temp_event[idx-1]
                else:
                    return_event = set_event
            else:
                if (time_now - click_next).total_seconds() < 1:
                    if idx == (len(set_event) - 1):
                        # Reached the end of the list, go back to the beginning
                        return_event = temp_event[0]
                    else:
                        # Increment the event if not the end of the list
                        # TODO: Increment to the next non-annotated waveform instead?
                        return_event = temp_event[idx+1]
                else:
                    return_event = set_event
        elif click_previous or click_next:
            if click_previous:
                if (time_now - click_previous).total_seconds() < 1:
                    if idx == 0:
                        # At the beginning of the list, go to the end
                        return_event = temp_event[-1]
                    else:
                        # Decrement the record if not the beginning of the list
                        # TODO: Decrement to the next non-annotated waveform instead?
                        return_event = temp_event[idx-1]
                else:
                    return_event = set_event
            else:
                if (time_now - click_next).total_seconds() < 1:
                    if idx == (len(set_event) - 1):
                        # Reached the end of the list, go back to the beginning
                        return_event = temp_event[0]
                    else:
                        # Increment the event if not the end of the list
                        # TODO: Increment to the next non-annotated waveform instead?
                        return_event = temp_event[idx+1]
                else:
                    return_event = set_event
        else:
            # Requested event
            return_event = set_event
    else:
        # Keep blank if loading main page (no presets)
        return_event = None

    return options_event, return_event


# Update the event text and set_event
@app.callback(
    [dash.dependencies.Output('event_text', 'children'),
     dash.dependencies.Output('set_record', 'value'),
     dash.dependencies.Output('set_event', 'value')],
    [dash.dependencies.Input('dropdown_rec', 'value'),
     dash.dependencies.Input('dropdown_event', 'value')])
def update_text(dropdown_rec, dropdown_event):
    # Get the header file
    event_text = html.Span([html.Br(), html.Br(), ''], style={'fontSize': event_fontsize})
    if dropdown_rec and dropdown_event:
        # Extract the records
        header_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_rec)
        temp_rec = wfdb.rdheader(header_path).seg_name
        temp_rec = [s for s in temp_rec if s != (dropdown_rec+'_layout') and s != '~']
        # Get the annotation information
        ann_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_rec)
        ann = wfdb.rdann(ann_path, 'cba')
        ann_event = ann.aux_note[temp_rec.index(dropdown_event)]
        # Update the annotation event text
        event_text = [
            html.Span([html.Br(), '{}'.format(ann_event)], style={'fontSize': event_fontsize})
        ]

    return event_text, dropdown_rec, dropdown_event


# Run the app using the chosen initial conditions
@app.callback(
    dash.dependencies.Output('the_graph', 'figure'),
    [dash.dependencies.Input('dropdown_event', 'value')],
    [dash.dependencies.State('dropdown_rec', 'value')])
def update_graph(dropdown_event, dropdown_rec):
    # The figure height and width
    fig_height = 725
    fig_width = 875
    # The figure margins
    margin_left = 0
    margin_top = 25
    margin_right = 0
    margin_bottom = 0
    # Grid and zero-line color
    gridzero_color = 'rgb(255, 60, 60)'
    # ECG gridlines parameters
    grid_delta_major = 0.2

    # Set a blank plot if none is loaded
    if not dropdown_rec or not dropdown_event:
        # Create baseline figure with 4 subplots
        fig = make_subplots(
            rows = 4,
            cols = 1,
            shared_xaxes = True,
            vertical_spacing = 0
        )
        # Update the layout to match the loaded state
        fig.update_layout({
            'height': fig_height,
            'width': fig_width,
            'margin': {'l': margin_left,
                       't': margin_top,
                       'r': margin_right,
                       'b': margin_bottom},
            'grid': {
                'rows': 4,
                'columns': 1,
                'pattern': 'independent'
            },
            'showlegend': False,
            'hovermode': 'x'
        })
        # Update the Null signal and axes
        for i in range(4):
            fig.add_trace(go.Scatter({
                'x': [None],
                'y': [None]
            }), row = i+1, col = 1)
            # Update axes based on signal type
            y_tick_vals = [round(n,1) for n in np.arange(0, 4, grid_delta_major).tolist()]
            y_tick_text = [str(n) if n%1 == 0 else ' ' for n in y_tick_vals]
            if (i == 0) or (i == 1):
                fig.update_xaxes({
                    'showgrid': True,
                    'dtick': grid_delta_major,
                    'showticklabels': False,
                    'gridcolor': gridzero_color,
                    'zeroline': True,
                    'zerolinewidth': 1,
                    'zerolinecolor': gridzero_color,
                    'gridwidth': 1,
                    'range': [0, 20],
                    'rangeslider': {
                        'visible': False
                    }
                }, row = i+1, col = 1)
                fig.update_yaxes({
                    'fixedrange': False,
                    'showgrid': True,
                    'tickvals': y_tick_vals,
                    'ticktext': y_tick_text,
                    'showticklabels': True,
                    'gridcolor': gridzero_color,
                    'zeroline': True,
                    'zerolinewidth': 1,
                    'zerolinecolor': gridzero_color,
                    'gridwidth': 1,
                    'range': [0, 4],
                }, row = i+1, col = 1)
            elif i == 3:
                fig.update_xaxes({
                    'title': 'Time (s)',
                    'showgrid': False,
                    'dtick': None,
                    'showticklabels': True,
                    'gridcolor': gridzero_color,
                    'zeroline': False,
                    'zerolinewidth': 1,
                    'zerolinecolor': gridzero_color,
                    'gridwidth': 1,
                    'range': [0, 20],
                    'rangeslider': {
                        'visible': False
                    }
                }, row = i+1, col = 1)
                fig.update_yaxes({
                    'fixedrange': False,
                    'showgrid': False,
                    'dtick': None,
                    'showticklabels': False,
                    'gridcolor': gridzero_color,
                    'zeroline': False,
                    'zerolinewidth': 1,
                    'zerolinecolor': gridzero_color,
                    'gridwidth': 1,
                    'range': [0, 4],
                }, row = i+1, col = 1)
            else:
                fig.update_xaxes({
                    'showgrid': False,
                    'dtick': None,
                    'showticklabels': False,
                    'gridcolor': gridzero_color,
                    'zeroline': False,
                    'zerolinewidth': 1,
                    'zerolinecolor': gridzero_color,
                    'gridwidth': 1,
                    'range': [0, 20],
                    'rangeslider': {
                        'visible': False
                    }
                }, row = i+1, col = 1)
                fig.update_yaxes({
                    'fixedrange': False,
                    'showgrid': False,
                    'dtick': None,
                    'showticklabels': False,
                    'gridcolor': gridzero_color,
                    'zeroline': False,
                    'zerolinewidth': 1,
                    'zerolinecolor': gridzero_color,
                    'gridwidth': 1,
                    'range': [0, 4],
                }, row = i+1, col = 1)

        return (fig)

    # Set some initial conditions
    record_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_event)
    record = wfdb.rdsamp(record_path)
    fs = record[1]['fs']
    n_sig = record[1]['n_sig']
    sig_name = record[1]['sig_name']
    sig_len = record[1]['sig_len']
    units = record[1]['units']

    # Maybe down-sample signal if too slow?
    down_sample = 8
    # Determine the time of the event (seconds)
    # `300` if standard 10 minute segment, `dropdown_event` otherwise
    event_time = 300
    # How much signal should be displayed before and after event (seconds)
    time_range = 30
    time_start = fs * (event_time - time_range)
    time_stop = fs * (event_time + time_range)
    # Determine how much signal to display before and after event (seconds)
    window_size = 5
    # Set the initial display range of y-values based on values in
    # initial range of x-values
    index_start = fs * (event_time - window_size)
    index_stop = fs * (event_time + window_size)

    # Set the initial layout of the figure
    fig = make_subplots(
        rows = 4,
        cols = 1,
        shared_xaxes = True,
        vertical_spacing = 0
    )
    fig.update_layout({
        'height': fig_height,
        'width': fig_width,
        'margin': {'l': margin_left,
                    't': margin_top,
                    'r': margin_right,
                    'b': margin_bottom},
        'grid': {
            'rows': n_sig,
            'columns': 1,
            'pattern': 'independent'
        },
        'showlegend': False,
        'hovermode': 'x',
        'spikedistance':  -1,
        'plot_bgcolor': '#ffffff',
        'paper_bgcolor': '#ffffff'
    })

    # Put all EKG signals before BP, then all others following
    sig_order = []
    extra_sigs = ['ABP', 'PLETH']
    if 'ABP' in sig_name:
        for i,s in enumerate(sig_name):
            if s not in extra_sigs:
                sig_order.append(i)
        sig_order.append(sig_name.index('ABP'))
        for s in extra_sigs[1:]:
            if s in sig_name:
                sig_order.append(sig_name.index(s))
    else:
        sig_order = range(n_sig)

    # Find unified range for all EKG signals
    total_y_vals = []
    total_y_range_vals = []
    for idx,r in enumerate(sig_order):
        if sig_name[r] not in extra_sigs:
            total_y_vals.append(record[0][:,r][time_start:time_stop:down_sample])
            total_y_range_vals.append(record[0][:,r][index_start:index_stop])
    min_y_vals = np.nanmin(total_y_range_vals)
    max_y_vals = np.nanmax(total_y_range_vals)
    min_tick = (round(np.nanmin(total_y_vals) / grid_delta_major) * grid_delta_major) - grid_delta_major
    max_tick = (round(np.nanmax(total_y_vals) / grid_delta_major) * grid_delta_major) + grid_delta_major

    # Name the axes to create the subplots
    for idx,r in enumerate(sig_order):
        x_string = 'x' + str(idx+1)
        y_string = 'y' + str(idx+1)
        # Generate the waveform x-values and y-values
        current_record = record[0][:,r]
        x_vals = [(i / fs) for i in range(sig_len)][time_start:time_stop:down_sample]
        y_vals = current_record[time_start:time_stop:down_sample]

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
            'name': sig_name[r]
        }), row = idx+1, col = 1)

        # Display where the event is
        fig.add_shape({
            'type': 'line',
            'x0': event_time,
            'y0': np.nanmin(y_vals) - 0.5 * (np.nanmax(y_vals) - np.nanmin(y_vals)),
            'x1': event_time,
            'y1': np.nanmax(y_vals) + 0.5 * (np.nanmax(y_vals) - np.nanmin(y_vals)),
            'xref': x_string,
            'yref': y_string,
            'line': {
                'color': 'Red',
                'width': 3
            }
        })

        # Set the initial y-axis parameters
        if sig_name[r] not in extra_sigs:
            grid_state = True
            dtick_state = grid_delta_major
            zeroline_state = True
            y_tick_vals = [round(n,1) for n in np.arange(min_tick, max_tick, grid_delta_major).tolist()]
            # Max text length to fit should be _
            y_tick_text = [str(n) if n%1 == 0 else ' ' for n in y_tick_vals]
        else:
            # Remove outliers to prevent weird axes scaling
            # temp_data = current_record[abs(current_record - np.nanmean(current_record)) < 3 * np.nanstd(current_record)]
            min_y_vals = np.nanmin(current_record[index_start:index_stop])
            max_y_vals = np.nanmax(current_record[index_start:index_stop])
            grid_state = False
            dtick_state = None
            zeroline_state = False
            x_tick_vals = []
            x_tick_text = []
            y_tick_vals = []
            y_tick_text = []

        # Set the initial x-axis parameters
        x_tick_vals = [round(n,1) for n in np.arange(event_time - time_range, event_time + time_range, grid_delta_major).tolist()]
        x_tick_text = [str(round(n)) if n%1 == 0 else '' for n in x_tick_vals]
        if idx != (n_sig - 1):
            fig.update_xaxes({
                'title': None,
                'dtick': 0.2,
                'showticklabels': False,
                'gridcolor': gridzero_color,
                'gridwidth': 1,
                'zeroline': zeroline_state,
                'zerolinewidth': 1,
                'zerolinecolor': gridzero_color,
                'range': [event_time - window_size, event_time + window_size],
                'showspikes': True,
                'spikemode': 'across',
                'spikesnap': 'cursor',
                'showline': True,
            }, row = idx+1, col = 1)
        else:
            # Add the x-axis title to the bottom figure
            fig.update_xaxes({
                'title': 'Time (s)',
                'dtick': 0.2,
                'showticklabels': True,
                'tickvals': x_tick_vals,
                'ticktext': x_tick_text,
                'gridcolor': gridzero_color,
                'gridwidth': 1,
                'zeroline': zeroline_state,
                'zerolinewidth': 1,
                'zerolinecolor': gridzero_color,
                'range': [event_time - window_size, event_time + window_size],
                'showspikes': True,
                'spikemode': 'across',
                'spikesnap': 'cursor',
                'showline': True,
            }, row = idx+1, col = 1)

        # Set the initial y-axis parameters
        fig.update_yaxes({
            'title': sig_name[r] + ' (' + units[r] + ')',
            'fixedrange': False,
            'showgrid': grid_state,
            'showticklabels': True,
            'tickvals': y_tick_vals,
            'ticktext': y_tick_text,
            'gridcolor': gridzero_color,
            'zeroline': zeroline_state,
            'zerolinewidth': 1,
            'zerolinecolor': gridzero_color,
            'gridwidth': 1,
            'range': [min_y_vals, max_y_vals],
        }, row = idx+1, col = 1)

        fig.update_traces(xaxis = x_string)

    return (fig)
