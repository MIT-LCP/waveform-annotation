# waveform-annotation
Platform for annotating physiological waveform data.

## Running local instance using Django server

- Install sqlite3: `sudo apt-get install sqlite3`.
- Create python environment with python 3.6: `python3 -m venv env`.
- Activate virtual python environment: `source env/bin/activate`.
- Install packages: `pip install -r requirements.txt`.
- Set up environment: `cp .env.example .env`.
- Within the `waveform-django` directory:
  - Run: `python manage.py runserver` to run the server.
- You should be able to access the waveform landing page at: <http://localhost:8000/waveform-annotation/waveforms/>
- If you would like to test out the email features:
  - Run: `python -m smtpd -n -c DebuggingServer localhost:1025` in another terminal tab. You should be able to see the content of the email which would have been sent on the live site. If you do not run this command first before testing out the email features, you will receive a `ConnectionRefusedError: [Errno 61] Connection refused` error.

## Basic server commands
- To migrate new models:
  - Run: `python manage.py migrate --run-syncdb`
- To reset the database:
  - Run: `python manage.py flush`
- After finished, deactivate virtual python environment: `deactivate`

## Viewing current annotations in database

- Using GraphQL API: Go to <http://localhost:8000/waveform-annotation/graphql?query={all_annotations{edges{node{user{username},record,event,decision,comments,decision_date}}}}> or other desired query as seen here ... <https://graphql.org/learn/queries/>
- Using SQLite3: `cd waveform-django`, `sqlite3 db.sqlite3`, then `select * from waveforms_annotation;`
