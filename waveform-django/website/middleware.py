from __future__ import absolute_import, division, print_function

try:
    from threading import local
except ImportError:
    from django.utils._threading_local import local

_thread_locals = local()


def get_current_request():
    """ returns the request object for this thread """
    return getattr(_thread_locals, "request", None)


def get_current_user():
    """ returns the current user, if exist, otherwise returns None """
    request = get_current_request()
    if request:
        temp_user = getattr(request, "user", None)
        return temp_user.username


def thread_local_middleware(get_response):
    # One-time configuration and initialization.
    def middleware(request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        _thread_locals.request = request
        response = get_response(request)
        # Code to be executed for each request/response after
        # the view is called.
        if hasattr(_thread_locals, "request"):
            del _thread_locals.request
        return response
    return middleware