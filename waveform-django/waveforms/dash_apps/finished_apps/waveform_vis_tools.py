import math
import os

import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import wfdb

from waveforms.models import User, UserSettings
from website.settings import base

from pathlib import Path


# Specify the record file locations
PROJECT_PATH = Path(base.HEAD_DIR)/'record-files'

# Load in the default variables
class WaveformVizTools:
    """
    Attributes: see `UserSettings` model.

    """
    def __init__(self, current_user):
        """
        Initialize WaveformVizTools

        Parameters
        ----------
        current_user : str
            The username of the current user.

        Returns
        -------
        N/A

        """
        self.CURRENT_USER = User.objects.get(username=current_user)
        self.USER_SETTINGS = UserSettings.objects.get(user=self.CURRENT_USER)
        self.FIG_HEIGHT = self.USER_SETTINGS.fig_height
        self.FIG_WIDTH = self.USER_SETTINGS.fig_width
        # The figure margins / padding around the graph div
        self.MARGIN_LEFT = self.USER_SETTINGS.margin_left
        self.MARGIN_TOP = self.USER_SETTINGS.margin_top
        self.MARGIN_RIGHT = self.USER_SETTINGS.margin_right
        self.MARGIN_BOTTOM = self.USER_SETTINGS.margin_bottom
        self.GRID_COLOR = self.USER_SETTINGS.grid_color
        self.BACKGROUND_COLOR = self.USER_SETTINGS.background_color
        self.SIG_COLOR = self.USER_SETTINGS.sig_color
        self.SIG_THICKNESS = self.USER_SETTINGS.sig_thickness
        self.ANN_COLOR = self.USER_SETTINGS.ann_color
        # EKG gridlines parameters (typically 0.2 as per paper standards)
        self.GRID_DELTA_MAJOR = self.USER_SETTINGS.grid_delta_major
        self.MAX_Y_LABELS = self.USER_SETTINGS.max_y_labels
        self.N_EKG_SIGS = self.USER_SETTINGS.n_ekg_sigs
        # Down-sample signal to increase performance: make higher if non-EKG
        # Average starting frequency = 250 Hz
        self.DOWN_SAMPLE_EKG = self.USER_SETTINGS.down_sample_ekg
        self.DOWN_SAMPLE = self.USER_SETTINGS.down_sample
        # How much signal should be displayed before and after the event
        # (seconds)
        self.TIME_RANGE_MIN = self.USER_SETTINGS.time_range_min
        self.TIME_RANGE_MAX = self.USER_SETTINGS.time_range_max
        # How much signal should be displayed initially before and after the
        # event (seconds)
        self.WINDOW_SIZE_MIN = self.USER_SETTINGS.window_size_min
        self.WINDOW_SIZE_MAX = self.USER_SETTINGS.window_size_max

        # Set the initial dragmode (`zoom`, `pan`, etc.)
        # For more info:
        # https://plotly.com/python/reference/layout/#layout-dragmode
        self.DRAG_MODE = False
        self.X_ZOOM_FIXED = True
        self.Y_ZOOM_FIXED = False
        # Set the initial y-axis parameters
        self.GRID_STATE = True
        self.ZEROLINE_STATE = False


    def get_subplot(self, rows):
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
            Represents the data used to define appearance of the figure
            (subplot layout, tick labels, etc.).

        """
        return make_subplots(
            rows = rows,
            cols = 1,
            shared_xaxes = True,
            vertical_spacing = 0.02
        )

    def get_layout(self, rows):
        """
        Generate a dictionary that is used to generate and format the layout
        of the figure. For more info:
        https://plotly.com/python/reference/layout/

        Parameters
        ----------
        rows : int
            The number of signals or desired graph figures.

        Returns
        -------
        N/A : dict
            Represents the layout of the figure.

        """
        return {
            # 'height': FIG_HEIGHT,
            # 'width': FIG_WIDTH,
            'margin': {'l': self.MARGIN_LEFT,
                       't': self.MARGIN_TOP,
                       'r': self.MARGIN_RIGHT,
                       'b': self.MARGIN_BOTTOM},
            'grid': {
                'rows': rows,
                'columns': 1,
                'pattern': 'independent'
            },
            'showlegend': False,
            'dragmode': self.DRAG_MODE,
            'spikedistance':  -1,
            'plot_bgcolor': self.BACKGROUND_COLOR,
            'paper_bgcolor': '#ffffff',
            'font_color': '#000000',
            'font': {
                'size': 12
            }
        }

    def get_trace(self, x_vals, y_vals, x_string, y_string, sig_name):
        """
        Generate a dictionary that is used to generate and format the signal
        trace of the figure. For more info:
        https://plotly.com/python/reference/scatter/#scatter

        Parameters
        ----------
        x_vals : list[float/int]
            The x-values to place the annotation.
        y_vals : list[float/int]
            The y-values to place the annotation.
        x_string : str
            Indicates which x-axis the signal belongs with.
        y_string : str
            Indicates which y-axis the signal belongs with.
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
            'hoverinfo': 'none',
            'type': 'scatter',
            'line': {
                'color': self.SIG_COLOR,
                'width': self.SIG_THICKNESS
            },
            'name': sig_name
        })

    def get_annotation(self, x_string):
        """
        Plot the annotations for the signal. Should always be at the x=0 line
        for viewing machine annotations. Make the line big enough to appear
        it's of infinite height on initial load, but limit its height to
        increase speed. For more info:
        https://plotly.com/python/reference/layout/shapes/#layout-shapes

        Parameters
        ----------
        x_string : str
            Which x-axis the annotation is bound to.

        Returns
        -------
        N/A : dict
            Represents the annotation shape for the plot.

        """
        return {
            'type': 'line',
            'x0': 0,
            'y0': 0,
            'x1': 0,
            'y1': 1,
            'xsizemode': 'pixel',
            'xanchor': 0,
            'xref': x_string,
            'yref': 'paper',
            'line': {
                'color': self.ANN_COLOR,
                'width': 3
            }
        }

    def get_xaxis(self, vals, show_ticks, title):
        """
        Generate a dictionary that is used to generate and format the x-axis
        for the figure. For more info:
        https://plotly.com/python/reference/scatter/#scatter-xaxis

        Parameters
        ----------
        vals : list[float/int]
            The tick values.
        show_ticks : bool
            Show the axis ticks and labels (True) or not (False).
        title : str
            The title to be placed on the x-axis.

        Returns
        -------
        N/A : dict
            Formatted information about the x-axis.

        """
        if show_ticks:
            tick_vals = [round(n,1) for n in np.arange(min(vals), max(vals), self.GRID_DELTA_MAJOR).tolist()]
            tick_text = [str(round(n)) if n%1 == 0 else '' for n in tick_vals]
        else:
            tick_vals = None
            tick_text = None

        return {
            'title': title,
            'fixedrange': self.X_ZOOM_FIXED,
            'dtick': 0.2,
            'showticklabels': show_ticks,
            'tickvals': tick_vals,
            'ticktext': tick_text,
            'tickangle': 0,
            'gridcolor': self.GRID_COLOR,
            'gridwidth': 1,
            'zeroline': self.ZEROLINE_STATE,
            'zerolinewidth': 1,
            'zerolinecolor': self.GRID_COLOR,
            'range': [-self.WINDOW_SIZE_MIN, self.WINDOW_SIZE_MAX],
            'rangeslider': {
                'visible': show_ticks,
                'thickness': 0.025,
                'bgcolor': 'rgb(255,255,255)'
            },
            'showspikes': True,
            'spikemode': 'across',
            'spikesnap': 'cursor',
            'spikedash': 'dot',
            'spikethickness': 1,
            'showline': True,
        }

    def get_yaxis(self, title, tick_vals, tick_text, min_val, max_val):
        """
        Generate a dictionary that is used to generate and format the y-axis
        for the figure. For more info:
        https://plotly.com/python/reference/scatter/#scatter-yaxis

        Parameters
        ----------
        title : str
            The title to be placed on the y-axis.
        tick_vals : list[float,int]
            The values where the ticks will be placed.
        tick_text : list[str]
            The label for each respective tick location.
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
            'fixedrange': self.Y_ZOOM_FIXED,
            'showgrid': self.GRID_STATE,
            'showticklabels': True,
            'tickvals': tick_vals,
            'ticktext': tick_text,
            'gridcolor': self.GRID_COLOR,
            'zeroline': self.ZEROLINE_STATE,
            'zerolinewidth': 1,
            'zerolinecolor': self.GRID_COLOR,
            'gridwidth': 1,
            'range': [min_val, max_val],
        }

    def get_dropdown(self, dropdown_value):
        """
        Retrieve the dropdown value from its dash context.

        Parameters
        ----------
        dropdown_value : list[dict], dict
            Either a list (if multiple input triggers) of dictionaries or a
            single dictionary (if single input trigger) of the current state
            of the app.

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

    def order_sigs(self, sig_name, exclude_sigs=[]):
        """
        Put all EKG signals before BP and RESP, then all others following.

        Parameters
        ----------
        sig_name : list[str]
            The list of signal names in the order from the WFDB record.
        exclude_sigs : list[int], optional
            The list of signal indices to be excluded since they have already
            been determined to have all 0s for the specified time range.

        Returns
        -------
        sig_order : list[str]
            The ordered list of signal names. Should only be 4 elements long.
        n_ekgs : int
            The total number of actual EKG signals.

        """
        sig_order = []
        # TODO: make case-insensitive
        ekg_sigs = ['II', 'V', 'V5', 'V1', 'V2', 'V3', 'V4', 'V6', 'I', 'III',
                    'aVR', 'AVR', 'aVF', 'AVF', 'aVL', 'AVL', 'MCL']
        bp_sigs = ['ABP', 'AR1', 'AR2', 'AR3', 'IBP1', 'IBP2', 'IBP3', 'IBP4',
                   'IBP5', 'IBP6', 'IBP7', 'IBP8']
        resp_sigs = ['PLETH', 'pleth']

        # Exclude signals which have all 0s
        itter_sig_name = [j for i,j in enumerate(sig_name) if i not in exclude_sigs]
        # Add a max of `N_EKG_SIGS` EKG signals, the any number of BP and Resp
        # If not possible, try again twice by adding in order
        # If still not filled, just return the non-full `sig_order`
        n_ekgs = 0
        for _ in range(3):
            for ekgs in ekg_sigs:
                if n_ekgs == self.N_EKG_SIGS:
                    break
                elif ekgs in itter_sig_name:
                    sig_order.append(sig_name.index(ekgs))
                    n_ekgs += 1
            if len(sig_order) < min(len(sig_name), 4):
                for bps in bp_sigs:
                    if (bps in itter_sig_name) and (sig_name.index(bps) not in sig_order):
                        sig_order.append(sig_name.index(bps))
                        break
                for resps in resp_sigs:
                    if (resps in itter_sig_name) and (sig_name.index(resps) not in sig_order):
                        sig_order.append(sig_name.index(resps))
                        break
                break

        return sig_order, n_ekgs

    def format_y_vals(self, sig_order, sig_name, n_ekgs, record, index_start,
                      index_stop):
        """
        Format the y-values and separate the EKG signals to window them
        together.

        Parameters
        ----------
        sig_order : list[int]
            The ordered list of signal names from `order_sigs`.
        sig_name : list[int]
            The list of signal names in the order from the WFDB record.
        n_ekgs : int
            The total number of expected EKG signals.
        record : wfdb.io.record.Record object
            The WFDB record for the signal.
        index_start : int
            Where to start reading the signal.
        index_stop : int
            Where to stop reading the signal.

        Returns
        -------
        all_y_vals : ndarray
            All of the signals, including the EKG signals.

        """
        all_y_vals = []
        for i,r in enumerate(sig_order):
            sig_name_index = sig_name.index(sig_name[r])
            if i < n_ekgs:
                current_y_vals = record[0][:,sig_name_index][index_start:index_stop:self.DOWN_SAMPLE_EKG]
            else:
                current_y_vals = record[0][:,sig_name_index][index_start:index_stop:self.DOWN_SAMPLE]
            current_y_vals = np.nan_to_num(current_y_vals).astype('float64')
            all_y_vals.append(current_y_vals)

        return all_y_vals

    def window_signal(self, y_vals):
        """
        Filter out extreme values from being shown on graph range. This uses
        the Coefficient of Variation (CV) approach to determine significant
        changes in the signal then return the adjusted minimum and maximum
        range... If a significant variation is signal is found then filter out
        extrema using normal distribution.

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
        # Standard deviation signal range to window
        std_range = self.USER_SETTINGS.signal_std
        # Get parameters of the signal
        temp_std = np.nanstd(y_vals)
        temp_mean = np.mean(y_vals[np.isfinite(y_vals)])
        temp_nan = np.all(np.isnan(y_vals))
        temp_zero = np.all(y_vals==0)
        if not temp_nan and not temp_zero:
            # Prevent `RuntimeWarning: invalid value encountered in
            #          double_scalars`
            # NOTE: I used to set a default range of +-1 if the signal was
            #       very small but I decided to do away with that since it
            #       messed too many signals up, especially for the
            #       `2021_data`.
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

    def create_blank_figure(self, n_rows=4):
        """
        Create a blank figure.

        Parameters
        ----------
        n_rows : int, optional
            The number of blank rows to display.

        Returns
        -------
        fig : plotly.graph_objects
            Represents the data used to define appearance of the figure
            (subplot layout, tick labels, etc.).

        """
        fig = self.get_subplot(n_rows)
        fig.update_layout(self.get_layout(n_rows))
        for idx in range(n_rows):
            n_vals = 100
            x_string = 'x' + str(idx+1)
            x_vals = np.linspace(-self.WINDOW_SIZE_MIN, self.WINDOW_SIZE_MAX,
                                 n_vals)
            y_string = 'y' + str(idx+1)
            y_vals = np.zeros(n_vals)
            fig.add_trace(
                self.get_trace(x_vals, y_vals, x_string, y_string, 'N/A'),
                row = idx+1, col = 1)

            fig.add_shape(self.get_annotation(x_string))

            if idx != (n_rows - 1):
                fig.update_xaxes(
                    self.get_xaxis(x_vals, False, None),
                    row = idx+1, col = 1)
            else:
                fig.update_xaxes(
                    self.get_xaxis(x_vals, True, 'Time Since Event (s)'),
                    row = idx+1, col = 1)

            fig.update_yaxes(
                self.get_yaxis(f'N/A (N/A)', [-1, 0, 1], ['-1', '0', '1'],
                               -1, 1),
                row = idx+1, col = 1)

            fig.update_traces(xaxis = x_string)

        return fig

    def get_graph_info(self, idx, index_stop, index_start, y_vals, fs):
        """
        Get all the information required for the graph.

        Parameters
        ----------
        idx : int
            The current index for the waveforms.
        index_stop : int
            Where to stop reading the signal.
        index_start : int
            Where to start reading the signal.
        y_vals : ndarray
            The y-values of the current signal.
        fs : float / int
            The sampling rate of the waveform (1/s).

        Returns
        -------
        x_vals : list[float/int]
            The x-values to place the annotation.
        y_vals : list[float/int]
            The y-values to place the annotation.
        x_string : str
            Indicates which x-axis the signal belongs with.
        y_string : str
            Indicates which y-axis the signal belongs with.
        y_tick_vals : list[float/int]
            The location of the y-axis ticks.
        y_tick_text : list[str]
            The labels of the y-axis ticks.
        min_y_vals : float, int
            The minimum y-value of the windowed signal.
        max_y_vals : float, int
            The maximum y-value of the windowed signal.

        """
        # Name the axes and create the subplots
        x_string = 'x' + str(idx+1)
        y_string = 'y' + str(idx+1)
        x_vals = [-self.TIME_RANGE_MIN + (i / fs) for i in range(index_stop-index_start)]
        # Remove outliers to prevent weird axes scaling if possible
        min_y_vals, max_y_vals = self.window_signal(y_vals)
        # Process the EKG signals first
        if idx < self.N_EKG_SIGS:
            x_vals = x_vals[::self.DOWN_SAMPLE_EKG]
            # Create the ticks
            min_val = round(self.GRID_DELTA_MAJOR * round(min_y_vals/self.GRID_DELTA_MAJOR), 1)
            max_val = round(self.GRID_DELTA_MAJOR * round(max_y_vals/self.GRID_DELTA_MAJOR), 1)
            y_tick_vals = [round(n,1) for n in np.arange(min_val, max_val, self.GRID_DELTA_MAJOR).tolist()]
            # Prevent too many from rendering
            n_repeats = 2
            while len(y_tick_vals) > 20:
                new_grid_delta = n_repeats * self.GRID_DELTA_MAJOR
                min_val = round(new_grid_delta * round(min_y_vals/new_grid_delta), 1)
                max_val = round(new_grid_delta * round(max_y_vals/new_grid_delta), 1)
                y_tick_vals = [round(n,1) for n in np.arange(min_val, max_val, new_grid_delta).tolist()]
                n_repeats += 1
            # Max text length to fit should be `MAX_Y_LABELS`, also prevent over-crowding
            y_text_vals = y_tick_vals[::math.ceil(len(y_tick_vals)/self.MAX_Y_LABELS)]
            # Create the labels
            y_tick_text = [str(n) if n in y_text_vals else ' ' for n in y_tick_vals]
        else:
            x_vals = x_vals[::self.DOWN_SAMPLE]
            # Max text length to fit should be `MAX_Y_LABELS`, also prevent over-crowding
            y_tick_vals = [round(n,1) for n in np.linspace(min_y_vals, max_y_vals, self.MAX_Y_LABELS).tolist()]
            # Create the labels
            y_tick_text = [str(n) for n in y_tick_vals]

        return (x_vals, y_vals, x_string, y_string, y_tick_vals, y_tick_text,
                min_y_vals, max_y_vals)

    def prepare_graph(self, dropdown_project, dropdown_record,
                      dropdown_event):
        """
        Read in the record and annotation and get some basic information.

        Parameters
        ----------
        dropdown_project : str
            Either a list (if multiple input triggers) of dictionaries or a
            single dictionary (if single input trigger) of the current
            project.
        dropdown_record : str
            Either a list (if multiple input triggers) of dictionaries or a
            single dictionary (if single input trigger) of the current event.
        dropdown_event : str
            Either a list (if multiple input triggers) of dictionaries or a
            single dictionary (if single input trigger) of the current record.

        Returns
        -------
        sig_order : list[str]
            The ordered list of signal names. Should only be 4 elements long.
        index_stop : int
            Where to stop reading the signal.
        index_start : int
            Where to start reading the signal.
        all_y_vals : ndarray
            All of the signals, including the EKG signals.
        sig_name : list[str]
            The list of signal names in the order from the WFDB record.
        units : list[str]
            The units for each of the signals.
        fs : float / int
            The sampling rate of the waveform (1/s).

        """
        # Determine the time of the event (seconds)
        event_path = str(PROJECT_PATH / dropdown_project / dropdown_record / dropdown_event)
        ann = wfdb.rdann(event_path, 'alm')
        event_time = (ann.sample / ann.fs)[0]

        # Determine the signal information
        record = wfdb.rdsamp(event_path, return_res=16)
        fs = record[1]['fs']
        sig_name = record[1]['sig_name']
        units = record[1]['units']

        # Set the initial display range of y-values based on values in
        # initial range of x-values
        index_start = int(fs * (event_time - self.TIME_RANGE_MIN))
        index_stop = int(fs * (event_time + self.TIME_RANGE_MAX))

        # Collect all of the signals and format their graph attributes
        sig_order, n_ekgs = self.order_sigs(sig_name)
        all_y_vals = self.format_y_vals(
            sig_order, sig_name, n_ekgs, record, index_start, index_stop
        )
        # Try to account for empty channels
        exclude_list = []
        while (len(sig_name) - len(exclude_list)) > 0:
            count_zero = 0
            for i,yv in enumerate(all_y_vals):
                # Discards a signal if all its values are <0.01 or the same
                if ((np.isclose(yv, np.zeros(len(yv)), atol=1e-2).all()) or
                (len(set(yv)) == 1)):
                    exclude_list.append(sig_order[i])
                    count_zero += 1
            if count_zero == 0:
                break
            else:
                # TODO Potential problem here? Got error TypeError: order_sigs() got multiple values for argument 'exclude_sigs' at v115l v115l_1m
                # but it went away after submitting again
                sig_order, n_ekgs = self.order_sigs(
                    n_ekgs, sig_name, exclude_sigs=exclude_list
                )
                all_y_vals = self.format_y_vals(
                    sig_order, sig_name, n_ekgs, record, index_start,
                    index_stop
                )

        return (fs, sig_name, units, index_start, index_stop, sig_order,
                all_y_vals)

    def create_final_figure(self, dropdown_project, dropdown_record,
                            dropdown_event):
        """
        Create the final figure.

        Parameters
        ----------
        dropdown_project : str
            Either a list (if multiple input triggers) of dictionaries or a
            single dictionary (if single input trigger) of the current
            project.
        dropdown_record : str
            Either a list (if multiple input triggers) of dictionaries or a
            single dictionary (if single input trigger) of the current
            event.
        dropdown_event : str
            Either a list (if multiple input triggers) of dictionaries or a
            single dictionary (if single input trigger) of the current
            record.

        Returns
        -------
        fig : plotly.graph_objects
            Represents the data used to define appearance of the figure
            (subplot layout, tick labels, etc.).

        """
        fs, sig_name, units, index_start, index_stop, sig_order, all_y_vals = self.prepare_graph(
            dropdown_project, dropdown_record, dropdown_event
        )

        # Sometimes there may not be 4 signals available to display
        n_sig = len(sig_order)
        # Set the initial layout of the figure
        fig = self.get_subplot(n_sig)
        fig.update_layout(self.get_layout(n_sig))

        # Name the axes and create the subplots
        for idx,r in enumerate(sig_order):
            x_vals, y_vals, x_string, y_string, y_tick_vals, y_tick_text, min_y_vals, max_y_vals = self.get_graph_info(
                idx, index_stop, index_start, all_y_vals[idx], fs
            )

            fig.add_trace(
                self.get_trace(x_vals, y_vals, x_string, y_string, sig_name[r]),
                row = idx+1, col = 1)

            if idx != (n_sig - 1):
                fig.update_xaxes(
                    self.get_xaxis(x_vals, False, None),
                    row = idx+1, col = 1)
            else:
                fig.add_shape(self.get_annotation(x_string))
                fig.update_xaxes(
                    self.get_xaxis(x_vals, True, 'Time Since Event (s)'),
                    row = idx+1, col = 1)

            fig.update_yaxes(
                self.get_yaxis(f'{sig_name[r]} ({units[r]})', y_tick_vals,
                               y_tick_text, min_y_vals, max_y_vals),
                row = idx+1, col = 1)

            fig.update_traces(xaxis = x_string)

        return fig
