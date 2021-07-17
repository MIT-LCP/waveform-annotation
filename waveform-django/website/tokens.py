import datetime

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import six


class UserTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # Reset the link every hour
        # TODO: Add a last_login field and incorporate this to the token in
        #       order to more robustly inactivate the link.
        t_now = datetime.datetime.now()
        t_epoch = datetime.datetime(1970, 1, 1)
        timestamp = int((t_now - t_epoch).total_seconds()/60/60)
        return (
            six.text_type(user.pk) + user.username +
            six.text_type(timestamp)
        )

password_reset_token = UserTokenGenerator()
