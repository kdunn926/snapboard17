SNAPBoard17 is a bulletin board application for the Django web framework.
It was originally written to run with Django 1.0 on Python 2.5, some changes
have been implemented to get it (mostly) running with Django 1.7 on Python 2.7.

Origianl Features (note: only basic forum functionality is verified to be working with Django 1.7):

    * Editable posts with all revisions publicly available
    * Messages posted within threads can be made visible only to selected 
      users
        * Not tested on Django 1.7
    * BBCode, Markdown and Textile supported for post formatting
    * BBCode toolbar
    * Multiple forums with four types of permissions
    * Forum permissions can be assigned to custom groups of users
    * Group administration can be delegated to end users on a per-group basis
    * Moderators for each forum
    * User preferences
    * Watched topics
    * Abuse reports
    * User and IP address bans that don't automatically spread to other Django
      applications within the project
    * i18n hooks to create your own translations
    * Included translations: French, Russian

SNAPBoard's original documentation is located in the docs/ directory. To build it in
HTML format, cd to docs/ and run ``make html``. Sphinx is required for this 
to work.

SNAPBoard depends on django-pagination, which can be found at 
http://code.google.com/p/django-pagination/.

You are free to use any package or custom application for extra features such 
as user profiles, private messaging or registration.

SNAPBoard is free software. If you would like to submit a patch or report a 
bug, please do so on the project's page at http://code.google.com/p/snapboard/.

