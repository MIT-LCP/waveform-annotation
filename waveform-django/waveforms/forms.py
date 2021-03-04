from django import forms

from waveforms.models import UserSettings


class GraphSettings(forms.ModelForm):
    """
    Allow the user to change their default graph settings.
    """
    class Meta:
        model = UserSettings
        fields = (
            'fig_height', 'fig_width', 'margin_left', 'margin_top',
            'margin_right', 'margin_bottom', 'grid_color', 'sig_color',
            'sig_thickness', 'ann_color', 'grid_delta_major',
            'max_y_labels', 'down_sample_ekg', 'down_sample',
            'time_range_min', 'time_range_max', 'window_size_min',
            'window_size_max'
        )
        help_texts = {
            'fig_height': """The figure height""",
            'fig_width': """The figure width""",
            'margin_left': """The left margin of the figure""",
            'margin_top': """The top margin of the figure""",
            'margin_right': """The right margin of the figure""",
            'margin_bottom': """The bottom margin of the figure""",
            'grid_color': """The grid color""",
            'sig_color': """The color of the signal""",
            'sig_thickness': """The thickness of the signal""",
            'ann_color': """The color of the annotation (zero-line)""",
            'grid_delta_major': """EKG gridlines parameters / spacing""",
            'max_y_labels': """Set the maximum number of y-axis labels per 
                signal""",
            'down_sample': """Down-sample non-EKG signals (usually higher 
                than EKG down-sampling rate)""",
            'down_sample_ekg': """Down-sample EKG signal to increase 
                performance (average starting frequency = 250 Hz)""",
            'time_range_min': """How much total signal should be displayed 
                before the event (seconds)""",
            'time_range_max': """How much total signal should be displayed 
                after the event (seconds)""",
            'window_size_min': """How much initial signal should be displayed 
                before the event (seconds)""",
            'window_size_max': """How much initial signal should be displayed 
                after the event (seconds)"""
        }
        widgets = {
            'fig_height': forms.NumberInput(attrs={'min': 0, 'type': 'number'}),
            'fig_width': forms.NumberInput(attrs={'min': 0, 'type': 'number'}),
            'margin_left': forms.NumberInput(attrs={'type': 'number'}),
            'margin_top': forms.NumberInput(attrs={'type': 'number'}),
            'margin_right': forms.NumberInput(attrs={'type': 'number'}),
            'margin_bottom': forms.NumberInput(attrs={'type': 'number'}),
            'grid_color': forms.TextInput(attrs={'type': 'color'}),
            'sig_color': forms.TextInput(attrs={'type': 'color'}),
            'sig_thickness': forms.NumberInput(attrs={'min': 0, 'type': 'number'}),
            'ann_color': forms.TextInput(attrs={'type': 'color'}),
            'grid_delta_major': forms.NumberInput(attrs={'min': 0, 'type': 'number'}),
            'max_y_labels': forms.NumberInput(attrs={'min': 1, 'type': 'number'}),
            'down_sample_ekg': forms.NumberInput(attrs={'min': 1, 'type': 'number'}),
            'down_sample': forms.NumberInput(attrs={'min': 1, 'type': 'number'}),
            'time_range_min': forms.NumberInput(attrs={'min': 0, 'max': 300, 'type': 'number'}),
            'time_range_max': forms.NumberInput(attrs={'min': 0, 'max': 300, 'type': 'number'}),
            'window_size_min': forms.NumberInput(attrs={'min': 0, 'max': 300, 'type': 'number'}),
            'window_size_max': forms.NumberInput(attrs={'min': 0, 'max': 300, 'type': 'number'}),
        }
        labels = {
            'fig_height': 'Figure height',
            'fig_width': 'Figure width',
            'margin_left': 'Left margin',
            'margin_top': 'Top margin',
            'margin_right': 'Right margin',
            'margin_bottom': 'Bottom margin',
            'grid_color': 'Grid color',
            'sig_color': 'Signal color',
            'sig_thickness': 'Signal thickness',
            'ann_color': 'Annotation color',
            'grid_delta_major': 'Grid delta',
            'max_y_labels': 'Maximum y-labels',
            'down_sample': 'Non-EKG downsample',
            'down_sample_ekg': 'EKG downsample',
            'time_range_min': 'Total time before event',
            'time_range_max': 'Total time after event',
            'window_size_min': 'Initial time before event',
            'window_size_max': 'Initial time after event'
        }

    def __init__(self, user, *args, **kwargs):
        """
        Initialize a settings model for the user
        """
        super().__init__(*args, **kwargs)
        self.user = user.username

    def clean(self):
        """
        Check for any invalid values that may break the code later
        """
        if self.errors:
            return

        if self.cleaned_data['window_size_min'] > self.cleaned_data['time_range_min']:
            raise forms.ValidationError('The initial minimum window must be less than the total minimum window')

        if self.cleaned_data['window_size_max'] > self.cleaned_data['time_range_max']:
            raise forms.ValidationError('The initial maximum window must be less than the total maximum window')

    def reset_default(self):
        """
        Reset all the values to their defaults
        """
        for f in self.instance._meta.fields:
            if f.name in set(self.fields):
                setattr(self.instance, f.name, f.default)
        self.instance.save()

    def save(self):
        """
        Save the cleaned form data
        """
        super().save()
