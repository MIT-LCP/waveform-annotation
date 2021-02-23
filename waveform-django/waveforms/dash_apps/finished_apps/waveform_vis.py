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
event_fontsize = '24px'
# Set the default configuration of the plot top buttons
plot_config = {
    'displayModeBar': True,
    'modeBarButtonsToRemove': [
        'hoverClosestCartesian',
        'hoverCompareCartesian',
        'toggleSpikelines'
    ],
    'modeBarButtonsToAdd': [
        'sendDataToCloud',
        'editInChartStudio',
        'resetViews'
    ]
}


# Initialize the Dash App
app = DjangoDash(name='waveform_graph', id='target_id', assets_folder='assets')
# Specify the app layout
app.layout = html.Div([
    # Area to submit annotations
    html.Div([
        # The record display
        html.Label(['Record:']),
        html.Div(
            id = 'dropdown_rec',
            children = html.Span([''], style={'fontSize': event_fontsize})
        ),
        # The event display
        html.Label(['Event:']),
        html.Div(
            id = 'dropdown_event',
            children = html.Span([''], style={'fontSize': event_fontsize})
        ),
        # The event display
        html.Label(['Event Type:']),
        html.Div(
            id = 'event_text',
            children = html.Span([''], style={'fontSize': event_fontsize})
        ),
        # The reviewer decision section
        html.Label(['Enter decision here:']),
        dcc.RadioItems(
            id = 'reviewer_decision',
            options = [
                {'label': 'True (alarm is correct)', 'value': 'True'},
                {'label': 'False (alarm is incorrect)', 'value': 'False'},
                {'label': 'Uncertain', 'value': 'Uncertain'}
            ],
            labelStyle = {'display': 'block'},
            style = {'width': dropdown_width},
            persistence = False
        ),
        html.Br(),
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
    ], style = {'display': 'inline-block', 'vertical-align': '75px'}),
    # The plot itself
    html.Div([
        dcc.Graph(
            id = 'the_graph',
            config = plot_config
        )
    ], style = {'display': 'inline-block'}),
    # Hidden div inside the app that stores the desired record and event
    dcc.Input(id = 'set_record', type = 'hidden', value = ''),
    dcc.Input(id = 'set_event', type = 'hidden', value = ''),
    # Hidden div inside the app that stores the current record and event
    dcc.Input(id = 'temp_record', type = 'hidden', value = ''),
    dcc.Input(id = 'temp_event', type = 'hidden', value = ''),
])


def get_header_info(file_path):
    header_path = os.path.join(PROJECT_PATH, file_path, file_path)
    file_contents = wfdb.rdheader(header_path).seg_name
    file_contents = [s for s in file_contents if s != (file_path+'_layout') and s != '~']
    return file_contents


# Clear/preset reviewer decision and comments
@app.callback(
    [dash.dependencies.Output('reviewer_decision', 'value'),
     dash.dependencies.Output('reviewer_comments', 'value')],
    [dash.dependencies.Input('temp_event', 'value')])
def clear_text(temp_event):
    current_user = get_current_user()
    if (temp_event != '') and (temp_event != None) and (current_user != ''):
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
        """.format(current_user, temp_event)
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
        """.format(current_user, temp_event)
        res = schema.execute(query)
        if res.data['all_annotations']['edges'] == []:
            reviewer_comments = ''
        else:
            reviewer_comments = res.data['all_annotations']['edges'][0]['node']['comments']
        return reviewer_decision, reviewer_comments
    else:
        return None, ''


# Dynamically update the record given the current record and event
@app.callback(
    [dash.dependencies.Output('dropdown_rec', 'children'),
     dash.dependencies.Output('dropdown_event', 'children')],
    [dash.dependencies.Input('previous_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('next_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('set_record', 'value')],
    [dash.dependencies.State('set_event', 'value'),
     dash.dependencies.State('temp_record', 'value'),
     dash.dependencies.State('temp_event', 'value'),
     dash.dependencies.State('reviewer_decision', 'value'),
     dash.dependencies.State('reviewer_comments', 'value')])
def get_record_event_options(click_previous, click_next, set_record, set_event,
                             record_value, event_value, decision_value, comments_value):
    # Determine what triggered this function
    ctx = dash.callback_context
    # Prepare to return the record and event value
    # Get the record file
    records_path = os.path.join(PROJECT_PATH, 'RECORDS')
    with open(records_path, 'r') as f:
        all_records = f.read().splitlines()

    if ctx.triggered:
        # Extract all the events
        all_events = get_header_info(record_value)

        # Determine what triggered the function
        click_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if click_id == 'previous_annotation':
            # Determine the record
            if all_events.index(event_value) > 0:
                # Event list not ended, keep record value the same
                return_record = record_value
            else:
                idr = all_records.index(record_value)
                if idr == 0:
                    # Reached the beginning of the list, go to the end
                    return_record = all_records[-1]
                else:
                    # Increment the record if not the end of the list
                    # TODO: Increment to the next non-annotated waveform instead?
                    return_record = all_records[idr-1]

            # Update the events if the record is updated
            if return_record != record_value:
                # Extract all the events
                all_events = get_header_info(return_record)
            # Check to see if overflow has occurred
            if event_value not in all_events:
                ide = len(all_events)
            else:
                ide = all_events.index(event_value)
            # Determine the event
            if ide == 0:
                # At the beginning of the list, go to the end
                return_event = all_events[-1]
            else:
                # Decrement the record if not the beginning of the list
                # TODO: Decrement to the next non-annotated waveform instead?
                return_event = all_events[ide-1]

        elif click_id == 'next_annotation':
            # Determine the record
            if all_events.index(event_value) < (len(all_events) - 1):
                # Event list not ended, keep record value the same
                return_record = record_value
            else:
                idr = all_records.index(record_value)
                if idr == (len(all_records) - 1):
                    # Reached the end of the list, go back to the beginning
                    return_record = all_records[0]
                else:
                    # Increment the record if not the end of the list
                    # TODO: Increment to the next non-annotated waveform instead?
                    return_record = all_records[idr+1]

            # Update the events if the record is updated
            if return_record != record_value:
                # Extract all the events
                all_events = get_header_info(return_record)
            # Check to see if overflow has occurred
            if event_value not in all_events:
                ide = -1
            else:
                ide = all_events.index(event_value)
            # Determine the event
            if ide == (len(all_events) - 1):
                # Reached the end of the list, go back to the beginning
                return_event = all_events[0]
            else:
                # Increment the event if not the end of the list
                # TODO: Increment to the next non-annotated waveform instead?
                return_event = all_events[ide+1]

        # Update the annotations: only save the annotations if a decision is made
        if decision_value:
            # Convert ms from epoch to datetime object
            if (click_id == 'previous_annotation'):
                submit_time = datetime.datetime.fromtimestamp(click_previous / 1000.0)
            elif (click_id == 'next_annotation'):
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
    else:
        # See if record and event was requested (never event without record)
        if set_record != '':
            return_record = set_record
            return_event = set_event
        else:
            # Start with the first record and event if first load
            return_record = all_records[0]
            all_events = get_header_info(return_record)
            return_event = all_events[0]

    # Update the annotation current record text
    return_record = [
        html.Span(['{}'.format(return_record)], style={'fontSize': event_fontsize})
    ]
    # Update the annotation current event text
    return_event = [
        html.Span(['{}'.format(return_event)], style={'fontSize': event_fontsize})
    ]

    return return_record, return_event


# Update the event text and set_event
@app.callback(
    [dash.dependencies.Output('event_text', 'children'),
     dash.dependencies.Output('temp_record', 'value'),
     dash.dependencies.Output('temp_event', 'value')],
    [dash.dependencies.Input('dropdown_rec', 'children'),
     dash.dependencies.Input('dropdown_event', 'children')])
def update_text(dropdown_rec, dropdown_event):
    # Get the header file
    event_text = html.Span([''], style={'fontSize': event_fontsize})
    # Determine the record
    try:
        dropdown_rec = dropdown_rec[0]['props']['children'][0]
    except KeyError:
        dropdown_rec = dropdown_rec['props']['children'][0]
    # Determine the event
    try:
        dropdown_event = dropdown_event[0]['props']['children'][0]
    except KeyError:
        dropdown_event = dropdown_event['props']['children'][0]
    if dropdown_rec and dropdown_event:
        # Extract the header contents
        temp_rec = get_header_info(dropdown_rec)
        # Get the annotation information
        ann_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_rec)
        ann = wfdb.rdann(ann_path, 'cba')
        ann_event = ann.aux_note[temp_rec.index(dropdown_event)]
        # Update the annotation event text
        event_text = [
            html.Span(['{}'.format(ann_event), html.Br(), html.Br()], style={'fontSize': event_fontsize})
        ]

    return event_text, dropdown_rec, dropdown_event


# Run the app using the chosen initial conditions
@app.callback(
    dash.dependencies.Output('the_graph', 'figure'),
    [dash.dependencies.Input('dropdown_event', 'children')],
    [dash.dependencies.State('dropdown_rec', 'children')])
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
    # The color and thickness of the signal
    sig_color = 'rgb(0, 0, 0)'
    sig_thickness = 1.5
    # The color of the annotation
    ann_color = 'rgb(60, 60, 200)'
    # ECG gridlines parameters
    grid_delta_major = 0.2
    # Set the maximum number of y-labels
    max_y_labels = 8
    # Down-sample signal to increase performance: make higher if non-EKG
    # Average starting frequency = 250 Hz
    down_sample_ekg = 8
    down_sample = 16
    # Determine the time of the event (seconds)
    # `300` if standard 10 minute segment, `dropdown_event` otherwise
    event_time = 300
    # How much signal should be displayed before and after event (seconds)
    time_range_min = 40
    time_range_max = 10
    # How much signal should be displayed initially before and after event (seconds)
    window_size_min = 10
    window_size_max = 1
    # Standard deviation signal range to window
    std_range = 2
    # Set the initial dragmode (`zoom`, `pan`, etc.)
    # For more info: https://plotly.com/python/reference/layout/#layout-dragmode
    drag_mode = 'pan'
    # Set the zoom restrictions
    x_zoom_fixed = False
    y_zoom_fixed = True
    # Determine the input record and event
    try:
        dropdown_rec = dropdown_rec[0]['props']['children'][0]
    except KeyError:
        dropdown_rec = dropdown_rec['props']['children'][0]
    try:
        dropdown_event = dropdown_event[0]['props']['children'][0]
    except KeyError:
        dropdown_event = dropdown_event['props']['children'][0]

    # Set some initial conditions
    record_path = os.path.join(PROJECT_PATH, dropdown_rec, dropdown_event)
    record = wfdb.rdsamp(record_path, return_res=16)
    fs = record[1]['fs']
    n_sig = record[1]['n_sig']
    sig_name = record[1]['sig_name']
    sig_len = record[1]['sig_len']
    units = record[1]['units']

    # Set the initial display range of y-values based on values in
    # initial range of x-values
    index_start = fs * (event_time - time_range_min)
    index_stop = fs * (event_time + time_range_max)

    # Set the initial layout of the figure
    # For more info: https://plotly.com/python/subplots/
    fig = make_subplots(
        rows = 4,
        cols = 1,
        shared_xaxes = True,
        vertical_spacing = 0
    )
    # For more info: https://plotly.com/python/reference/layout/
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
        'dragmode': drag_mode,
        'spikedistance':  -1,
        'plot_bgcolor': '#ffffff',
        'paper_bgcolor': '#ffffff',
        'font': {
            'size': 12
        }
    })

    # Put all EKG signals before BP and RESP, then all others following
    sig_order = []
    ekg_sigs = {'II', 'III', 'V'}
    bp_sigs = {'ABP'}
    resp_sigs = {'RESP'}
    if any(x not in ekg_sigs for x in sig_name):
        for i,s in enumerate(sig_name):
            if s in ekg_sigs:
                sig_order.append(i)
        # TODO: Could maybe do this faster using sets
        for bps in bp_sigs:
            if bps in sig_name:
                sig_order.append(sig_name.index(bps))
        for resps in resp_sigs:
            if resps in sig_name:
                sig_order.append(sig_name.index(resps))
        for s in [y for x,y in enumerate(sig_name) if x not in set(sig_order)]:
            sig_order.append(sig_name.index(s))
    else:
        sig_order = range(n_sig)

    # Collect all the signals
    all_y_vals = []
    ekg_y_vals = []
    for r in sig_order:
        sig_name_index = sig_name.index(sig_name[r])
        if sig_name[r] in ekg_sigs:
            current_y_vals = record[0][:,sig_name_index][index_start:index_stop:down_sample_ekg]
        else:
            current_y_vals = record[0][:,sig_name_index][index_start:index_stop:down_sample]
        current_y_vals = np.nan_to_num(current_y_vals).astype('float64')
        all_y_vals.append(current_y_vals)
        # Find unified range for all EKG signals
        if sig_name[r] in ekg_sigs:
            ekg_y_vals.append(current_y_vals)

    # NOTE: Assuming there are always EKG signals
    # Flatten and change data type to prevent overflow
    ekg_y_vals = np.stack(ekg_y_vals).flatten()
    # Filter out extreme values from being shown on graph range
    # This uses the Coefficient of Variation (CV) approach to determine
    # significant changes in the signal... If a significant variation in
    # signal is found then filter out extrema using normal distribution
    # TODO: Prevent repeat code for non-EKG signals
    temp_std = np.nanstd(ekg_y_vals)
    temp_mean = np.mean(ekg_y_vals[np.isfinite(ekg_y_vals)])
    temp_nan = np.all(np.isnan(ekg_y_vals))
    temp_zero = np.all(ekg_y_vals==0)
    if not temp_nan and not temp_zero:
        # Prevent `RuntimeWarning: invalid value encountered in double_scalars`
        # TODO: Lazy fix but need to think about this more
        if (abs(temp_std / temp_mean) > 0.1) and (temp_std > 0.25):
            ekg_y_vals = ekg_y_vals[abs(ekg_y_vals - temp_mean) < std_range * temp_std]
            min_ekg_y_vals = np.nanmin(ekg_y_vals)
            max_ekg_y_vals = np.nanmax(ekg_y_vals)
        else:
            min_ekg_y_vals = np.nanmin(ekg_y_vals) - 1
            max_ekg_y_vals = np.nanmax(ekg_y_vals) + 1
    else:
        # Set default min and max values if all NaN or 0
        min_ekg_y_vals = -1
        max_ekg_y_vals = 1
    # Create the ticks based off of the range of y-values
    min_ekg_tick = (round(min_ekg_y_vals / grid_delta_major) * grid_delta_major) - grid_delta_major
    max_ekg_tick = (round(max_ekg_y_vals / grid_delta_major) * grid_delta_major) + grid_delta_major

    # Name the axes to create the subplots
    for idx,r in enumerate(sig_order):
        x_string = 'x' + str(idx+1)
        y_string = 'y' + str(idx+1)
        # Generate the waveform x-values and y-values
        y_vals = all_y_vals[idx]
        # Set the initial y-axis parameters
        if sig_name[r] in ekg_sigs:
            # Generate the x-values
            x_vals = [-time_range_min + (i / fs) for i in range(index_stop-index_start)][::down_sample_ekg]
            min_y_vals = min_ekg_y_vals
            max_y_vals = max_ekg_y_vals
            grid_state = True
            dtick_state = grid_delta_major
            zeroline_state = False
            # Create the ticks
            y_tick_vals = [round(n,1) for n in np.arange(min_ekg_tick, max_ekg_tick, grid_delta_major).tolist()][1:-1]
            # Max text length to fit should be `max_y_labels`, also prevent over-crowding
            y_text_vals = y_tick_vals[::math.ceil(len(y_tick_vals)/max_y_labels)]
            # Create the labels
            y_tick_text = [str(n) if n in y_text_vals else ' ' for n in y_tick_vals]
        else:
            # Generate the x-values
            x_vals = [-time_range_min + (i / fs) for i in range(index_stop-index_start)][::down_sample]
            # Remove outliers to prevent weird axes scaling if possible
            # TODO: Refactor this!
            temp_std = np.nanstd(y_vals)
            temp_mean = np.mean(y_vals[np.isfinite(y_vals)])
            temp_nan = np.all(np.isnan(y_vals))
            temp_zero = np.all(y_vals==0)
            if not temp_nan and not temp_zero:
                # Prevent `RuntimeWarning: invalid value encountered in double_scalars`
                # TODO: Lazy fix but need to think about this more
                if (abs(temp_std / temp_mean) > 0.1) and (temp_std > 0.25):
                    y_vals = y_vals[abs(y_vals - temp_mean) < std_range * temp_std]
                    min_y_vals = np.nanmin(y_vals)
                    max_y_vals = np.nanmax(y_vals)
                else:
                    min_y_vals = np.nanmin(y_vals) - 1
                    max_y_vals = np.nanmax(y_vals) + 1
            else:
                # Set default min and max values if all NaN or 0
                min_y_vals = -1
                max_y_vals = 1

            grid_state = True
            dtick_state = None
            zeroline_state = False
            x_tick_vals = []
            x_tick_text = []
            # Max text length to fit should be `max_y_labels`, also prevent over-crowding
            y_tick_vals = [round(n,1) for n in np.linspace(min_y_vals, max_y_vals, max_y_labels).tolist()][1:-1]
            # Create the labels
            y_tick_text = [str(n) for n in y_tick_vals]

        # Create the signal to plot
        # For more info: https://plotly.com/python/reference/scatter/#scatter
        fig.add_trace(go.Scatter({
            'x': x_vals,
            'y': y_vals.astype('float16'),
            'xaxis': x_string,
            'yaxis': y_string,
            'type': 'scatter',
            'line': {
                'color': sig_color,
                'width': sig_thickness
            },
            'name': sig_name[r]
        }), row = idx+1, col = 1)
        # Display where the event is
        # For more info: https://plotly.com/python/reference/layout/shapes/#layout-shapes
        fig.add_shape({
            'type': 'line',
            'x0': 0,
            'y0': min_y_vals - 0.5 * (max_y_vals - min_y_vals),
            'x1': 0,
            'y1': max_y_vals + 0.5 * (max_y_vals - min_y_vals),
            'xref': x_string,
            'yref': y_string,
            'line': {
                'color': ann_color,
                'width': 3
            }
        })

        # Set the initial x-axis parameters
        # For more info: https://plotly.com/python/reference/scatter/#scatter-xaxis
        x_tick_vals = [round(n,1) for n in np.arange(min(x_vals), max(x_vals), grid_delta_major).tolist()]
        x_tick_text = [str(round(n)) if n%1 == 0 else '' for n in x_tick_vals]
        if idx != (n_sig - 1):
            fig.update_xaxes({
                'title': None,
                'fixedrange': x_zoom_fixed,
                'dtick': 0.2,
                'showticklabels': False,
                'gridcolor': gridzero_color,
                'gridwidth': 1,
                'zeroline': zeroline_state,
                'zerolinewidth': 1,
                'zerolinecolor': gridzero_color,
                'range': [-window_size_min, window_size_max],
                'showspikes': True,
                'spikemode': 'across',
                'spikesnap': 'cursor',
                'showline': True,
            }, row = idx+1, col = 1)
        else:
            # Add the x-axis title to the bottom figure
            fig.update_xaxes({
                'title': 'Time Since Event (s)',
                'fixedrange': x_zoom_fixed,
                'dtick': 0.2,
                'showticklabels': True,
                'tickvals': x_tick_vals,
                'ticktext': x_tick_text,
                'gridcolor': gridzero_color,
                'gridwidth': 1,
                'zeroline': zeroline_state,
                'zerolinewidth': 1,
                'zerolinecolor': gridzero_color,
                'range': [-window_size_min, window_size_max],
                'showspikes': True,
                'spikemode': 'across',
                'spikesnap': 'cursor',
                'showline': True,
            }, row = idx+1, col = 1)

        # Set the initial y-axis parameters
        # For more info: https://plotly.com/python/reference/scatter/#scatter-yaxis
        fig.update_yaxes({
            'title': sig_name[r] + ' (' + units[r] + ')',
            'fixedrange': y_zoom_fixed,
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
