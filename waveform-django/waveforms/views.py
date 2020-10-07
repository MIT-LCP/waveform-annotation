from django.shortcuts import render


def waveform_published_home(request):
    """
    Render waveform main page for published databases.

    Parameters
    ----------
    N/A : N/A

    Returns
    -------
    N/A : HTML page / template variable
        HTML webpage responsible for hosting the waveform plot. Also pass
        through the project slug and version as variables for use both in
        the template and the waveform app.

    """

    return render(request, 'waveforms/home.html')
