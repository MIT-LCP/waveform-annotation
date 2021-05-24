# waveform-django
This directory houses all of the code for the annotator and static content for the website.

## export

- Contains all of the setup and testing for the GraphQL API.

## static

- Contains all of the static content for the website (e.g. packages, favicons, CSS, JS, etc.)

## templates

- Contains all of the base Django templates (augmented HTML) for the website.

## waveforms

- Contains the waveform annotator code and Django template for its rendering.

## website

- Contains all of the Django templates for the visible website except for the annotator itself.

## manage.py

- Allows the user to interact with the Django database. Examples include:
<pre><code>./manage.py runserver
./manage.py migrate
./manage.py makemigrations
</code></pre>

## schema.py

- Sets up the interaction between the Django models / database and the GraphQL API. For example, this line specifies that we should base our queries off of the <code>Query</code> class and prevent the conversion of <i>snake_case</i> class names to <i>CamelCase</i>:
<pre><code>schema = graphene.Schema(query=Query, auto_camelcase=False)</code></pre>
- The URL defined to interact with this endpoint is <code>waveform-django/export/urls.py</code>.
