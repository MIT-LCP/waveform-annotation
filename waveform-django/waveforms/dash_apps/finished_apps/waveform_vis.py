import os
import wfdb
import math
import csv
import pytz
import datetime
import numpy as np
import pandas as pd
import django.core.cache
from website.middleware import get_current_user
from website.settings import base
from waveforms.models import User, Annotation, UserSettings
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
ALL_PROJECTS = base.ALL_PROJECTS
# Formatting settings
sidebar_width = '210px'
event_fontsize = '24px'
comment_box_height = '300px'
label_fontsize = '20px'
button_height = '35px'
submit_width = str(float(sidebar_width.split('px')[0]) / 2) + 'px'
arrow_width = str(float(submit_width.split('px')[0]) / 2 + 3) + 'px'
# Set the default configuration of the plot top buttons
plot_config = {
    'displayModeBar': True,
    'modeBarButtonsToRemove': [
        'hoverClosestCartesian',
        'hoverCompareCartesian',
        'toggleSpikelines',
        'zoom2d',
        'resetScale2d'
    ]
}


# Initialize the Dash App
app = DjangoDash(name='waveform_graph', id='target_id', assets_folder='assets')
# Specify the app layout
app.layout = html.Div([
    dcc.Loading(id = 'loading-1', children = [
        # Area to submit annotations
        html.Div([
            # The project display
            html.Label(['Project:']),
            html.Div(
                id = 'dropdown_project',
                children = html.Span([''], style={'fontSize': event_fontsize})
            ),
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
            html.Label(['Enter decision here:'],
                       style = {'font-size': label_fontsize}),
            dcc.RadioItems(
                id = 'reviewer_decision',
                options = [
                    {'label': 'True (alarm is correct)', 'value': 'True'},
                    {'label': 'False (alarm is incorrect)', 'value': 'False'},
                    {'label': 'Uncertain / Save for later', 'value': 'Uncertain'}
                ],
                labelStyle = {'display': 'block'},
                style = {'width': sidebar_width,},
                persistence = False
            ),
            html.Br(),
            # The reviewer comment section
            html.Label(['Enter comments here:'],
                       style = {'font-size': label_fontsize}),
            html.Div(
                dcc.Textarea(id = 'reviewer_comments',
                             style = {
                                'width': sidebar_width,
                                'height': comment_box_height,
                                'font-size': label_fontsize
                             })
            ),
            # Submit annotation decision and comments
            html.Button('Submit',
                        id = 'submit_annotation',
                        style = {'height': button_height,
                                 'width': submit_width,
                                 'font-size': 'large'}),
            # Select previous or next annotation
            html.Button('\u2190',
                        id = 'previous_annotation',
                        style = {'height': button_height,
                                 'width': arrow_width,
                                 'font-size': 'large'}),
            html.Button('\u2192',
                        id = 'next_annotation',
                        style = {'height': button_height,
                                 'width': arrow_width,
                                 'font-size': 'large'}),
        ], style = {'display': 'inline-block', 'vertical-align': '35px',
                    'padding-right': '10px'}),
        # The plot itself
        html.Div([
            dcc.Graph(
                id = 'the_graph',
                config = plot_config
            ),
        ], style = {'display': 'inline-block'})
    ], type = 'default'),
    # Hidden div inside the app that stores the desired project, record, and event
    dcc.Input(id = 'set_project', type = 'hidden', value = ''),
    dcc.Input(id = 'set_record', type = 'hidden', value = ''),
    dcc.Input(id = 'set_event', type = 'hidden', value = ''),
    # Hidden div inside the app that stores the current project, record, and event
    dcc.Input(id = 'temp_project', type = 'hidden', value = ''),
    dcc.Input(id = 'temp_record', type = 'hidden', value = ''),
    dcc.Input(id = 'temp_event', type = 'hidden', value = ''),
])


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

    user_ann = Annotation.objects.filter(user=user, project=project_folder)
    event_list += [a.event for a in user_ann if a not in event_list]

    return event_list


def get_user_records(user):
    """
    Get the records assigned to a user in the CSV file.

    Parameters
    ----------
    user : User
        The User whose records will be retrieved.
    project_folder : str
        The project used to retrieve the records.

    Returns
    -------
    N/A: dict
        The records assigned to the user by project.

    """
    annotations = Annotation.objects.filter(user=user)

    user_events = {}
    for project in ALL_PROJECTS:
        user_events[project] = get_user_events(user, project)

    # Get all user records
    user_records = {}
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


def get_subplot(rows):
    """
    Create a graph layout based on the number of input signals (rows). For
    more info:
    https://plotly.com/python/subplots/

    Parameters
    ----------
    rows : int
        The number of signals or desired graph figures.

    Returns
    -------
    N/A : plotly.graph_objects
        Represents the data used to define appearance of the figure (subplot
        layout, tick labels, etc.).

    """
    return make_subplots(
        rows = rows,
        cols = 1,
        shared_xaxes = True,
        vertical_spacing = 0.02
    )


def get_layout(fig_height, fig_width, margin_left, margin_top, margin_right,
               margin_bottom, rows, drag_mode, background_color):
    """
    Generate a dictionary that is used to generate and format the layout of
    the figure. For more info:
    https://plotly.com/python/reference/layout/

    Parameters
    ----------
    fig_height : float
        The height of the figure's SVG div.
    fig_width : float
        The width of the figure's SVG div.
    margin_left : float
        How much margin should be to the left of the figure.
    margin_top : float
        How much margin should be at the top of the figure.
    margin_right : float
        How much margin should be to the right of the figure.
    margin_bottom : float
        How much margin should be at the bottom of the figure.
    rows : int
        The number of signals or desired graph figures.
    drag_mode : str
        Set the initial dragmode (zoom, pan, etc.). See more here:
        https://plotly.com/javascript/reference/#layout-dragmode.
    background_color : str
        Set the color of the background paper of the signal. This should be
        in six-figure hexadecimal format (ex. '#ffffff').

    Returns
    -------
    N/A : dict
        Represents the layout of the figure.

    """
    return {
        'height': fig_height,
        'width': fig_width,
        'margin': {'l': margin_left,
                   't': margin_top,
                   'r': margin_right,
                   'b': margin_bottom},
        'grid': {
            'rows': rows,
            'columns': 1,
            'pattern': 'independent'
        },
        'showlegend': False,
        'hovermode': 'x',
        'dragmode': drag_mode,
        'spikedistance':  -1,
        'plot_bgcolor': background_color,
        'paper_bgcolor': '#ffffff',
        'font_color': '#000000',
        'font': {
            'size': 12
        }
    }


def get_trace(x_vals, y_vals, x_string, y_string, sig_color, sig_thickness,
              sig_name):
    """
    Generate a dictionary that is used to generate and format the signal trace
    of the figure. For more info:
    https://plotly.com/python/reference/scatter/#scatter

    Parameters
    ----------
    x_vals : list[float,int]
        The x-values to place the annotation.
    y_vals : list[float,int]
        The y-values to place the annotation.
    x_string : str
        Indicates which x-axis the signal belongs with.
    y_string : str
        Indicates which y-axis the signal belongs with.
    sig_color : str
        A string of the RGB representation of the desired signal color.
        Ex: 'rgb(20,40,100)'
    sig_thickness : float, int
        Specifies the thickness of the signal.
    sig_name : str
        The name of the signal.

    Returns
    -------
    N/A : dict
        Represents the layout of the signal.

    """
    return go.Scatter({
        'x': x_vals,
        'y': y_vals.astype('float16'),
        'xaxis': x_string,
        'yaxis': y_string,
        'type': 'scatter',
        'line': {
            'color': sig_color,
            'width': sig_thickness
        },
        'name': sig_name
    })


def get_annotation(min_val, max_val, x_string, y_string, ann_color):
    """
    Plot the annotations for the signal. Should always be at the x=0 line for
    viewing machine annotations. Make the line big enough to appear it's of
    infinite height on initial load, but limit its height to increase speed.
    For more info:
    https://plotly.com/python/reference/layout/shapes/#layout-shapes

    Parameters
    ----------
    min_val : float, int
        The minimum value of the signal.
    max_val : float, int
        The maximum value of the signal.
    x_string : str
        Which x-axis the annotation is bound to.
    y_string : str
        Which y-axis the annotation is bound to.
    ann_color : str
        A string of the RGB representation of the desired annotation color.
        Ex: 'rgb(20,40,100)'

    Returns
    -------
    N/A : dict
        Represents the annotation shape for the plot.

    """
    y_range = max_val - min_val
    y_start = min_val - (0.5 * y_range)
    y_stop = max_val + (0.5 * y_range)

    return {
        'type': 'line',
        'x0': 0,
        'y0': y_start,
        'x1': 0,
        'y1': y_stop,
        'xref': x_string,
        'yref': y_string,
        'line': {
            'color': ann_color,
            'width': 3
        }
    }


def get_xaxis(vals, grid_delta_major, show_ticks, title, zoom_fixed, grid_color,
              zeroline_state, window_size_min, window_size_max):
    """
    Generate a dictionary that is used to generate and format the x-axis for
    the figure. For more info:
    https://plotly.com/python/reference/scatter/#scatter-xaxis

    Parameters
    ----------
    vals : list[float,int]
        The tick values.
    grid_delta_major : float, int
        The spacing of the gridlines.
    show_ticks : bool
        Show the axis ticks and labels (True) or not (False).
    title : str
        The title to be placed on the x-axis.
    zoom_fixed : bool
        If True, prevent the user from scaling the x-axis. This applies to
        both the horizontal drag animation on the x-axis and "Zoom" button
        when selecting the bounding box.
    grid_color : str
        A string of the RGB representation of the desired color.
        Ex: `rgb(20,40,100)`
    zeroline_state : bool
        Display the zeroline on the grid (True) or not (False).
    window_size_min : float, int
        The initial minimum range to display on the x-axis.
    window_size_max : float, int
        The initial maximum range to display on the x-axis.

    Returns
    -------
    N/A : dict
        Formatted information about the x-axis.

    """
    if show_ticks:
        tick_vals = [round(n,1) for n in np.arange(min(vals), max(vals), grid_delta_major).tolist()]
        tick_text = [str(round(n)) if n%1 == 0 else '' for n in tick_vals]
    else:
        tick_vals = None
        tick_text = None

    return {
        'title': title,
        'fixedrange': zoom_fixed,
        'dtick': 0.2,
        'showticklabels': show_ticks,
        'tickvals': tick_vals,
        'ticktext': tick_text,
        'tickangle': 0,
        'gridcolor': grid_color,
        'gridwidth': 1,
        'zeroline': zeroline_state,
        'zerolinewidth': 1,
        'zerolinecolor': grid_color,
        'range': [-window_size_min, window_size_max],
        'showspikes': True,
        'spikemode': 'across',
        'spikesnap': 'cursor',
        'showline': True,
    }


def get_yaxis(title, zoom_fixed, grid_state, tick_vals, tick_text, grid_color,
              zeroline_state, min_val, max_val):
    """
    Generate a dictionary that is used to generate and format the y-axis for
    the figure. For more info:
    https://plotly.com/python/reference/scatter/#scatter-yaxis

    Parameters
    ----------
    title : str
        The title to be placed on the y-axis.
    zoom_fixed : bool, optional
        If True, prevent the user from scaling the y-axis. This applies to
        both the vertical drag animation on the y-axis and "Zoom" button when
        selecting the bounding box.
    grid_state : bool
        Display the grid on the y-axis (True) or not (False).
    tick_vals : list[float,int]
        The values where the ticks will be placed.
    tick_text : list[str]
        The label for each respective tick location.
    grid_color : str, optional
        A string of the RGB representation of the desired color.
        Ex: `rgb(20,40,100)`
    zeroline_state : bool
        Display the zeroline on the grid (True) or not (False).
    min_val : float, int
        The minimum value of the signal.
    max_val : float, int
        The maximum value of the signal.

    Returns
    -------
    N/A : dict
        Formatted information about the y-axis.

    """
    return {
        'title': title,
        'fixedrange': zoom_fixed,
        'showgrid': grid_state,
        'showticklabels': True,
        'tickvals': tick_vals,
        'ticktext': tick_text,
        'gridcolor': grid_color,
        'zeroline': zeroline_state,
        'zerolinewidth': 1,
        'zerolinecolor': grid_color,
        'gridwidth': 1,
        'range': [min_val, max_val],
    }


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


def get_current_ann():
    """
    Returns either the record or event value of the current annotation.

    Parameters
    ----------
    N/A

    Returns
    -------
    N/A : str
        The current record.
    N/A : str
        The current event.
    N/A : str
        The current project.

    """
    # Get the current user's annotations
    current_user = User.objects.get(username=get_current_user())
    user_annotations = Annotation.objects.filter(user=current_user)
    completed_events = []
    for a in user_annotations:
        completed_events.append([a.project, a.event])

    all_events = []
    for project in ALL_PROJECTS:
        proj_events = get_user_events(current_user, project)
        for event in proj_events:
            all_events.append([project, event])

    # Get the earliest annotation
    ann_indices = sorted([all_events.index(a) for a in completed_events])

    if ann_indices:
        try:
            current_event = next(a for a, b in enumerate(ann_indices, 0) if a != b)
        except StopIteration:
            if (ann_indices[-1]+1) == len(all_events):
                current_event = 0
            else:
                current_event = ann_indices[-1] + 1
    else:
        current_event = 0

    if all_events != []:
        return all_events[current_event][1].split('_')[0], all_events[current_event][1],\
            all_events[current_event][0]
    else:
        return 'N/A', 'N/A', 'N/A'


def get_dropdown(dropdown_value):
    """
    Retrieve the dropdown value from its dash context.

    Parameters
    ----------
    dropdown_value : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current state of the app.

    Returns
    -------
    dropdown_value : str
        The current selected dropdown.

    """
    try:
        dropdown_value = dropdown_value[0]['props']['children'][0]
    except KeyError:
        dropdown_value = dropdown_value['props']['children'][0]
    return dropdown_value


def order_sigs(n_ekg_sigs, sig_name, exclude_sigs=[]):
    """
    Put all EKG signals before BP and RESP, then all others following.

    Parameters
    ----------
    n_ekg_sigs : int
        The total number of expected EKG signals.
    sig_name : list[str]
        The list of signal names in the order from the WFDB record.
    exclude_sigs : list[int], optional
        The list of signal indices to be excluded since they have already
        been determined to have all 0s for the specified time range.

    Returns
    -------
    sig_order : list[str]
        The ordered list of signal names. Should only be 4 elements long.

    """
    sig_order = []
    ekg_sigs = ['II', 'V', 'V5', 'V1', 'V2', 'V3', 'V4', 'V6', 'I', 'III',
                'aVR', 'aVF', 'aVL']
    bp_sigs = ['ABP', 'IBP1', 'IBP2', 'IBP5', 'IBP6', 'CVP', 'ICP', 'LAP',
               'PAP']
    resp_sigs = ['PLETH', 'Resp', 'CO2']

    # Exclude signals which have all 0s
    itter_sig_name = [j for i,j in enumerate(sig_name) if i not in exclude_sigs]
    # Add a max of `n_ekg_sigs` EKG signals, the any number of BP and Resp.
    # If not possible, try again twice by adding in order.
    # If still not filled, just return the non-full `sig_order`.
    n_ekgs = 0
    for _ in range(3):
        for ekgs in ekg_sigs:
            if n_ekgs == n_ekg_sigs:
                break
            elif ekgs in itter_sig_name:
                sig_order.append(sig_name.index(ekgs))
                n_ekgs += 1
        if len(sig_order) < 4:
            for bps in bp_sigs:
                if (bps in itter_sig_name) and (sig_name.index(bps) not in sig_order):
                    sig_order.append(sig_name.index(bps))
                    break
            for resps in resp_sigs:
                if (resps in itter_sig_name) and (sig_name.index(resps) not in sig_order):
                    sig_order.append(sig_name.index(resps))
                    break

    return sig_order


def format_y_vals(sig_order, sig_name, n_ekg_sigs, record, index_start,
                  index_stop, down_sample_ekg, down_sample):
    """
    Format the y-values and separate the EKG signals to window them together.

    Parameters
    ----------
    sig_order : list[int]
        The ordered list of signal names from `order_sigs`.
    sig_name : list[int]
        The list of signal names in the order from the WFDB record.
    n_ekg_sigs : int
        The total number of expected EKG signals.
    record : wfdb.io.record.Record object
        The WFDB record for the signal.
    index_start : int
        Where to start reading the signal.
    index_stop : int
        Where to stop reading the signal.
    down_sample_ekg : int
        The amount of downsampling for EKG signals.
    down_sample : int
        The amount of downsampling for non-EKG signals.

    Returns
    -------
    ekg_y_vals : ndarray
        Only the EKG signals.
    all_y_vals : ndarray
        All of the signals, including the EKG signals.

    """
    all_y_vals = []
    ekg_y_vals = []
    for i,r in enumerate(sig_order):
        sig_name_index = sig_name.index(sig_name[r])
        if i < n_ekg_sigs:
            current_y_vals = record[0][:,sig_name_index][index_start:index_stop:down_sample_ekg]
        else:
            current_y_vals = record[0][:,sig_name_index][index_start:index_stop:down_sample]
        current_y_vals = np.nan_to_num(current_y_vals).astype('float64')
        all_y_vals.append(current_y_vals)
        # Find unified range for all EKG signals
        if i < n_ekg_sigs:
            ekg_y_vals.append(current_y_vals)

    # NOTE: Assuming there are always EKG signals
    ekg_y_vals = np.stack(ekg_y_vals).flatten()
    return ekg_y_vals, all_y_vals


def window_signal(y_vals):
    """
    Filter out extreme values from being shown on graph range. This uses the
    Coefficient of Variation (CV) approach to determine significant changes in
    the signal then return the adjusted minimum and maximum range... If a
    significant variation is signal is found then filter out extrema using
    normal distribution.

    Parameters
    ----------
    y_vals : numpy array
        The y-values of the signal.

    Returns
    -------
    min_y_vals : float, int
        The minimum y-value of the windowed signal.
    max_y_vals : float, int
        The maximum y-value of the windowed signal.

    """
    # Load in the default variables
    current_user = User.objects.get(username=get_current_user())
    user_settings = UserSettings.objects.get(user=current_user)
    # Standard deviation signal range to window
    std_range = user_settings.signal_std
    # Get parameters of the signal
    temp_std = np.nanstd(y_vals)
    temp_mean = np.mean(y_vals[np.isfinite(y_vals)])
    temp_nan = np.all(np.isnan(y_vals))
    temp_zero = np.all(y_vals==0)
    if not temp_nan and not temp_zero:
        # Prevent `RuntimeWarning: invalid value encountered in double_scalars`
        # NOTE: I used to set a default range of +-1 if the signal was very
        #       small but I decided to do away with that since it messed too
        #       many signals up, especially for the `2021_data`.
        new_y_vals = y_vals[abs(y_vals - temp_mean) < std_range * temp_std]
        if (len(new_y_vals) == 0) or (len(new_y_vals) == len(y_vals)):
            min_y_vals = np.nanmin(y_vals) - temp_std
            max_y_vals = np.nanmax(y_vals) + temp_std
        else:
            min_y_vals = np.nanmin(new_y_vals)
            max_y_vals = np.nanmax(new_y_vals)
    else:
        # Set default min and max values if all NaN or 0
        min_y_vals = -1
        max_y_vals = 1
    return min_y_vals, max_y_vals


@app.callback(
    [dash.dependencies.Output('reviewer_decision', 'value'),
     dash.dependencies.Output('reviewer_comments', 'value')],
    [dash.dependencies.Input('temp_event', 'value'),
     dash.dependencies.Input('temp_project', 'value')])
def clear_text(temp_event, temp_project):
    """
    Clear the reviewer decision and comments if none has been created or load
    them otherwise when loading a new record and event.

    Parameters
    ----------
    temp_event : str
        The current event.
    temp_project : str
        The current project
    Returns
    -------
    N/A : str
        The decision of the user.
    N/A : str
        The comments of the user.

    """
    current_user = get_current_user()
    if (temp_event != '') and (temp_event is not None) and (current_user != ''):
        # Get the decision
        user = User.objects.get(username=current_user)
        try:
            res = Annotation.objects.get(
                user=user, project=temp_project, event=temp_event)
            reviewer_decision = res.decision
            reviewer_comments = res.comments
        except Annotation.DoesNotExist:
            reviewer_decision = None
            reviewer_comments = ''
        return reviewer_decision, reviewer_comments
    else:
        return None, ''


@app.callback(
    [dash.dependencies.Output('dropdown_rec', 'children'),
     dash.dependencies.Output('dropdown_event', 'children'),
     dash.dependencies.Output('dropdown_project', 'children')],
    [dash.dependencies.Input('submit_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('previous_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('next_annotation', 'n_clicks_timestamp'),
     dash.dependencies.Input('set_project', 'value'),
     dash.dependencies.Input('set_record', 'value')],
    [dash.dependencies.State('set_event', 'value'),
     dash.dependencies.State('temp_project', 'value'),
     dash.dependencies.State('temp_record', 'value'),
     dash.dependencies.State('temp_event', 'value'),
     dash.dependencies.State('reviewer_decision', 'value'),
     dash.dependencies.State('reviewer_comments', 'value')])
def get_record_event_options(click_submit, click_previous, click_next,
                             set_project, set_record, set_event, project_value,
                             record_value, event_value, decision_value, comments_value):
    """
    Dynamically update the record given the current record and event.

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

    """
    # Determine what triggered this function
    ctx = dash.callback_context
    # Prepare to return the record and event value
    # Get the record file
    current_user = User.objects.get(username=get_current_user())
    all_records = get_user_records(current_user)
    if ctx.triggered:
        # Determine what triggered the function
        click_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if click_id == 'previous_annotation':
            # Determine the project
            all_events = get_header_info(project_value, record_value)
            if all_records[project_value].index(record_value) > 0 or \
                    all_events.index(event_value) > 0:
                # Project list not ended, keep project value the same
                return_project = project_value
            else:
                idr = ALL_PROJECTS.index(project_value)
                if idr == 0:
                    # Reached beginning of project list, go to end
                    idr = -1
                    while len(all_records[ALL_PROJECTS[idr]]) == 0:
                        idr -= 1
                    return_project = ALL_PROJECTS[idr]
                else:
                    # Decrement the project if not the end of the list
                    idr -= 1
                    while len(all_records[ALL_PROJECTS[idr]]) == 0:
                        idr -= 1
                        if idr == -1:
                            idr = len(ALL_PROJECTS) - 1
                    return_project = ALL_PROJECTS[idr]

            # Update the records/events to use correct project
            all_records = all_records[return_project]

            # Determine the record
            if return_project != project_value:
                return_record = all_records[-1]
            elif all_events.index(event_value) > 0:
                # Event list not ended, keep record value the same
                return_record = record_value
            else:
                idr = all_records.index(record_value)
                if idr == 0:
                    # Reached the beginning of the list, go to the end
                    return_record = all_records[-1]
                else:
                    # Decrement the record if not the end of the list
                    # TODO: Increment to the next non-annotated waveform instead?
                    return_record = all_records[idr-1]

            # Update the events if the record is updated
            all_events = get_header_info(return_project, return_record)
            if return_record != record_value:
                # Extract all the events
                all_events = [e for e in all_events if e.find(return_record) != -1]

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

        elif (click_id == 'next_annotation') or (click_id == 'submit_annotation'):
            # Determine the project
            all_events = get_header_info(project_value, record_value)
            if all_records[project_value].index(record_value) < \
                    (len(all_records[project_value]) - 1) or \
                    all_events.index(event_value) < (len(all_events)-1):
                # Project list not ended, keep project value the same
                return_project = project_value
            else:
                idr = ALL_PROJECTS.index(project_value)
                if idr == (len(ALL_PROJECTS) - 1):
                    # Reached end of project list, go to front
                    idr = 0
                    while len(all_records[ALL_PROJECTS[idr]]) == 0:
                        idr += 1
                    return_project = ALL_PROJECTS[idr]
                else:
                    # Increment the project if not the end of the list
                    idr += 1
                    while len(all_records[ALL_PROJECTS[idr]]) == 0:
                        idr += 1
                        if idr == len(ALL_PROJECTS):
                            idr = 0
                    return_project = ALL_PROJECTS[idr]

            # Update the records to use correct project
            all_records = all_records[return_project]

            # Determine the record
            if return_project != project_value and len(all_records) > 0:
                return_record = all_records[0]
            elif all_events.index(event_value) < (len(all_events) - 1):
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
            all_events = get_header_info(return_project, return_record)
            if return_record != record_value:
                # Extract all the events
                all_events = [e for e in all_events if e.find(return_record) != -1]

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

        # Update the annotations: only save the annotations if a decision is
        # made and the submit button was pressed
        if decision_value and (click_id == 'submit_annotation'):
            # Convert ms from epoch to datetime object (localize to the time
            # zone in the settings)
            submit_time = datetime.datetime.fromtimestamp(click_submit / 1000.0)
            set_timezone = pytz.timezone(base.TIME_ZONE)
            submit_time = set_timezone.localize(submit_time)
            # Save the annotation to the database only if changes
            # were made or a new annotation
            current_user = User.objects.get(username=get_current_user())
            try:
                res = Annotation.objects.get(user=current_user,
                                             project=return_project,
                                             event=event_value)
                current_annotation = [res.project, res.record, res.event,
                                      res.decision, res.comments]
                proposed_annotation = [project_value, event_value,
                                       decision_value, comments_value]
                # Only save annotation if something has changed
                if current_annotation[:4] != proposed_annotation:
                    annotation = Annotation(
                        user = current_user,
                        project = project_value,
                        record = record_value,
                        event = event_value,
                        decision = decision_value,
                        comments = comments_value,
                        decision_date = submit_time
                    )
                    annotation.update()
            except Annotation.DoesNotExist:
                # Create new annotation since none already exist
                annotation = Annotation(
                    user = current_user,
                    project = project_value,
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
            return_project = set_project
            return_record = set_record
            return_event = set_event
        else:
            return_record, return_event, return_project = get_current_ann()

    # Update the annotation current project text
    return_project = [
        html.Span(['{}'.format(return_project)], style={'fontSize': event_fontsize})
    ]
    # Update the annotation current record text
    return_record = [
        html.Span(['{}'.format(return_record)], style={'fontSize': event_fontsize})
    ]
    # Update the annotation current event text
    return_event = [
        html.Span(['{}'.format(return_event)], style={'fontSize': event_fontsize})
    ]
    return return_record, return_event, return_project


@app.callback(
    [dash.dependencies.Output('event_text', 'children'),
     dash.dependencies.Output('temp_record', 'value'),
     dash.dependencies.Output('temp_event', 'value'),
     dash.dependencies.Output('temp_project', 'value')],
    [dash.dependencies.Input('dropdown_rec', 'children'),
     dash.dependencies.Input('dropdown_event', 'children'),
     dash.dependencies.Input('dropdown_project', 'children')])
def update_text(dropdown_rec, dropdown_event, dropdown_project):
    """
    Update the event text and set_event.

    Parameters
    ----------
    dropdown_project : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current project.
    dropdown_rec : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current record.
    dropdown_event : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current event.

    Returns
    -------
    event_text : list[html.Span object]
        The current event in HTML form so it can be rendered on the page.
    dropdown_rec : str
        The new selected record.
    dropdown_event
        The new selected event.

    """
    # Get the header file
    event_text = html.Span([''], style={'fontSize': event_fontsize})
    # Determine the record
    dropdown_rec = get_dropdown(dropdown_rec)
    # Determine the event
    dropdown_event = get_dropdown(dropdown_event)
    # Determine project
    dropdown_project = get_dropdown(dropdown_project)

    if dropdown_rec and dropdown_event and dropdown_project:
        if ((dropdown_rec == 'N/A') or (dropdown_event == 'N/A') or
           (dropdown_project == 'N/A')):
            event_text = [
                html.Span(['N/A', html.Br(), html.Br()], style={'fontSize': event_fontsize})
            ]
        else:
            # Get the annotation information
            ann_path = os.path.join(PROJECT_PATH, dropdown_project,
                                    dropdown_rec, dropdown_event)
            ann = wfdb.rdann(ann_path, 'alm')
            ann_event = ann.aux_note[0]
            # Update the annotation event text
            event_text = [
                html.Span(['{}'.format(ann_event), html.Br(), html.Br()], style={'fontSize': event_fontsize})
            ]

    return event_text, dropdown_rec, dropdown_event, dropdown_project


@app.callback(
    dash.dependencies.Output('the_graph', 'figure'),
    [dash.dependencies.Input('dropdown_event', 'children')],
    [dash.dependencies.State('dropdown_rec', 'children'),
     dash.dependencies.State('dropdown_project', 'children')])
def update_graph(dropdown_event, dropdown_rec, dropdown_project):
    """
    Run the app and render the waveforms using the chosen initial conditions.

    Parameters
    ----------
    dropdown_event : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current record.
    dropdown_rec : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current event.
    dropdown_project : list[dict], dict
        Either a list (if multiple input triggers) of dictionaries or a single
        dictionary (if single input trigger) of the current project.
    Returns
    -------
    N/A : plotly.subplots
        The final figure.

    """
    # Load in the default variables
    current_user = User.objects.get(username=get_current_user())
    user_settings = UserSettings.objects.get(user=current_user)
    fig_height = user_settings.fig_height
    fig_width = user_settings.fig_width
    # The figure margins / padding around the graph div
    margin_left = user_settings.margin_left
    margin_top = user_settings.margin_top
    margin_right = user_settings.margin_right
    margin_bottom = user_settings.margin_bottom
    grid_color = user_settings.grid_color
    background_color = user_settings.background_color
    sig_color = user_settings.sig_color
    sig_thickness = user_settings.sig_thickness
    ann_color = user_settings.ann_color
    # EKG gridlines parameters (typically 0.2 as per paper standards)
    grid_delta_major = user_settings.grid_delta_major
    max_y_labels = user_settings.max_y_labels
    n_ekg_sigs = user_settings.n_ekg_sigs
    # Down-sample signal to increase performance: make higher if non-EKG
    # Average starting frequency = 250 Hz
    down_sample_ekg = user_settings.down_sample_ekg
    down_sample = user_settings.down_sample
    # How much signal should be displayed before and after the event (seconds)
    time_range_min = user_settings.time_range_min
    time_range_max = user_settings.time_range_max
    # How much signal should be displayed initially before and after the
    # event (seconds)
    window_size_min = user_settings.window_size_min
    window_size_max = user_settings.window_size_max

    # Determine the time of the event (seconds)
    # `300` if standard 10 minute segment, `dropdown_event` otherwise
    event_time = 300
    # Set the initial dragmode (`zoom`, `pan`, etc.)
    # For more info: https://plotly.com/python/reference/layout/#layout-dragmode
    drag_mode = 'pan'
    x_zoom_fixed = False
    y_zoom_fixed = False
    # Set the initial y-axis parameters
    grid_state = True
    zeroline_state = False
    dropdown_rec = get_dropdown(dropdown_rec)
    dropdown_event = get_dropdown(dropdown_event)
    dropdown_project = get_dropdown(dropdown_project)

    if ((dropdown_rec == 'N/A') or (dropdown_event == 'N/A') or
       (dropdown_project == 'N/A')):
        fig = get_subplot(4)
        fig.update_layout(
            get_layout(fig_height, fig_width, margin_left, margin_top,
                       margin_right, margin_bottom, 4, drag_mode,
                       background_color)
        )
        for idx in range(4):
            n_vals = 100
            x_string = 'x' + str(idx+1)
            x_vals = np.linspace(-window_size_min, window_size_max, n_vals)
            y_string = 'y' + str(idx+1)
            y_vals = np.zeros(n_vals)
            fig.add_trace(
                get_trace(x_vals, y_vals, x_string, y_string, sig_color,
                          sig_thickness, 'N/A'),
                row = idx+1, col = 1)

            fig.add_shape(
                get_annotation(-1, 1, x_string, y_string, ann_color)
            )

            if idx != (4 - 1):
                fig.update_xaxes(
                    get_xaxis(x_vals, grid_delta_major, False, None,
                            x_zoom_fixed, grid_color, zeroline_state,
                            window_size_min, window_size_max),
                    row = idx+1, col = 1)
            else:
                fig.update_xaxes(
                    get_xaxis(x_vals, grid_delta_major, True, 'Time Since Event (s)',
                            x_zoom_fixed, grid_color, zeroline_state,
                            window_size_min, window_size_max),
                    row = idx+1, col = 1)

            fig.update_yaxes(
                get_yaxis(f'N/A (N/A)', y_zoom_fixed, grid_state,
                          [-1, 0, 1], ['-1', '0', '1'], grid_color,
                          zeroline_state, -1, 1),
                row = idx+1, col = 1)

            fig.update_traces(xaxis = x_string)

        return (fig)

    record_path = os.path.join(PROJECT_PATH, dropdown_project,
                               dropdown_rec, dropdown_event)
    record = wfdb.rdsamp(record_path, return_res=16)
    fs = record[1]['fs']
    sig_name = record[1]['sig_name']
    sig_len = record[1]['sig_len']
    units = record[1]['units']

    # Set the initial display range of y-values based on values in
    # initial range of x-values
    index_start = int(fs * (event_time - time_range_min))
    index_stop = int(fs * (event_time + time_range_max))

    # Collect all of the signals and format their graph attributes
    sig_order = order_sigs(n_ekg_sigs, sig_name)
    ekg_y_vals, all_y_vals = format_y_vals(sig_order, sig_name, n_ekg_sigs,
                                           record, index_start, index_stop,
                                           down_sample_ekg, down_sample)
    # Try to account for empty channels
    exclude_list = []
    while (len(sig_name) - len(exclude_list)) > 4:
        count_zero = 0
        for i,yv in enumerate(all_y_vals):
            if (yv == 0).all():
                exclude_list.append(sig_order[i])
                sig_order = order_sigs(n_ekg_sigs, sig_name,
                                       exclude_sigs=exclude_list)
                ekg_y_vals, all_y_vals = format_y_vals(
                    sig_order, sig_name, n_ekg_sigs, record, index_start,
                    index_stop, down_sample_ekg, down_sample
                )
                count_zero += 1
        if count_zero == 0:
            break

    min_ekg_y_vals, max_ekg_y_vals = window_signal(ekg_y_vals)
    # Create the ticks based off of the range of y-values
    min_ekg_tick = min(ekg_y_vals)
    max_ekg_tick = max(ekg_y_vals)

    # Sometimes there may not be 4 signals available to display
    n_sig = len(sig_order)
    # Set the initial layout of the figure
    fig = get_subplot(n_sig)
    fig.update_layout(
        get_layout(fig_height, fig_width, margin_left, margin_top,
                   margin_right, margin_bottom, n_sig, drag_mode,
                   background_color)
    )

    # Name the axes and create the subplots
    for idx,r in enumerate(sig_order):
        x_string = 'x' + str(idx+1)
        y_string = 'y' + str(idx+1)
        x_vals = [-time_range_min + (i / fs) for i in range(index_stop-index_start)]
        y_vals = all_y_vals[idx]
        if idx < n_ekg_sigs:
            x_vals = x_vals[::down_sample_ekg]
            min_y_vals = min_ekg_y_vals
            max_y_vals = max_ekg_y_vals
            # Create the ticks
            y_tick_vals = [round(n,1) for n in np.arange(min_ekg_tick, max_ekg_tick, grid_delta_major).tolist()][1:-1]
            # Max text length to fit should be `max_y_labels`, also prevent over-crowding
            y_text_vals = y_tick_vals[::math.ceil(len(y_tick_vals)/max_y_labels)]
            # Create the labels
            y_tick_text = [str(n) if n in y_text_vals else ' ' for n in y_tick_vals]
        else:
            x_vals = x_vals[::down_sample]
            # Remove outliers to prevent weird axes scaling if possible
            min_y_vals, max_y_vals = window_signal(y_vals)
            # Max text length to fit should be `max_y_labels`, also prevent over-crowding
            y_tick_vals = [round(n,1) for n in np.linspace(min_y_vals, max_y_vals, max_y_labels).tolist()][1:-1]
            # Create the labels
            y_tick_text = [str(n) for n in y_tick_vals]

        fig.add_trace(
            get_trace(x_vals, y_vals, x_string, y_string, sig_color,
                      sig_thickness, sig_name[r]),
            row = idx+1, col = 1)

        fig.add_shape(
            get_annotation(min_y_vals, max_y_vals, x_string, y_string,
                           ann_color))

        if idx != (n_sig - 1):
            fig.update_xaxes(
                get_xaxis(x_vals, grid_delta_major, False, None, x_zoom_fixed,
                          grid_color, zeroline_state, window_size_min,
                          window_size_max),
                row = idx+1, col = 1)
        else:
            fig.update_xaxes(
                get_xaxis(x_vals, grid_delta_major, True,
                          'Time Since Event (s)', x_zoom_fixed, grid_color,
                          zeroline_state, window_size_min, window_size_max),
                row = idx+1, col = 1)

        fig.update_yaxes(
            get_yaxis(f'{sig_name[r]} ({units[r]})', y_zoom_fixed, grid_state,
                      y_tick_vals, y_tick_text, grid_color, zeroline_state,
                      min_y_vals, max_y_vals),
            row = idx+1, col = 1)

        fig.update_traces(xaxis = x_string)

    return (fig)
