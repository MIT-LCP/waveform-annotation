# waveform-annotation
Platform for annotating physiological waveform data.

## Running Local Instance Using Django Server

- Install sqlite3: `sudo apt-get install sqlite3`.
- Create python environment with python 3.6: `python3 -m venv env`.
- Activate virtual python environment: `source env/bin/activate`.
- Install packages: `pip install -r requirements.txt`.
- Set up environment: `cp .env.example .env`.
- Within the `waveform-django` directory:
  - Run: `python manage.py runserver` to run the server.
- After finished, deactivate virtual python environment: `deactivate`
