"""This module provides a Notifier class.

The Notifier can be used to notifier listeners.
"""


class Notifier(object):
    """Notifies all registered listeners."""

    def __init__(self, listener):
        """Constructs a new notifier object.

        listener is a list of listener objects.

        """
        super(Notifier, self).__init__()
        self.listener = listener

    def _notify(self, method, *args, **kwargs):
        """Notify all registered listeners.

        The return values for each call on the listener
        are saved and returned as a list.

        """
        rets = []
        for listener in self.listener:
            meth = getattr(listener, method)
            rets.append(meth(*args, **kwargs))
        return rets
