"""This module provides a ListInfo class.

It can be used to manage a list consisting of multiple named
sublists.
"""


class ListInfo(object):
    """Manage various lists."""

    def __init__(self, *listnames, **listdata):
        """Constructs a new ListInfo object.

        For each listname in listnames an empty
        list will be created.
        For each listname in listdata an attribute
        will be created which is initialized with the
        corresponding data.

        """
        super(ListInfo, self).__init__()
        self._listnames = list(listnames)
        for listname in self._listnames:
            setattr(self, listname, [])
        self._listnames.extend(listdata.keys())
        for listname, data in listdata.iteritems():
            setattr(self, listname, data)

    def append(self, entry, listname):
        """Append entry to list listname."""
        getattr(self, listname).append(entry)

    def remove(self, entry):
        """Remove entry from each list."""
        for listname in self._listnames:
            l = getattr(self, listname)
            setattr(self, listname, [f for f in l if f != entry])

    def _list_iter(self):
        for listname in self._listnames:
            yield getattr(self, listname)

    def __contains__(self, entry):
        for l in self._list_iter():
            if entry in l:
                return True
        return False

    def __iter__(self):
        for l in self._list_iter():
            for entry in l:
                yield entry
