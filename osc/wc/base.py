"""Higher-level classes and functions which are common to
project and package wc's."""

import os


def no_pending_transaction(meth):
    """Raise PendingTransactionError if a pending transaction exists.

    The exception is only raised if a rollback is not
    possible.
    Otherwise meth is returned.
    Can be used to decorate methods which should not be executed
    if a pending transaction exists.

    """
    def wrapper(self, *args, **kwargs):
        state = self._pending_transaction()
        if state is not None and not state.rollback(self.path):
            raise PendingTransactionError(state.name)
        return meth(self, *args, **kwargs)
    return wrapper


def no_conflicts(meth):
    """Raise a FileConflictError if there are conflicts.

    If no FileConflictError is raised meth is returned.
    Can be used to decorate methods which should not be executed
    if there are conflicts.

    """
    def wrapper(self, *args, **kwargs):
        conflicts = self.has_conflicts()
        if conflicts:
            raise FileConflictError(conflicts)
        return meth(self, *args, **kwargs)
    return wrapper


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


class TransactionListener(object):
    """Notify a client about a transaction.

    This way clients can examine the current status of
    update and commit.

    """
    def begin(self, name, uinfo):
        """Signal the beginning of a transaction.

        name is the name of the transaction.
        uinfo is an instance of class UpdateInfo or
        FileUpdateInfo.
        If this method returns False the transaction
        won't be executed.

        """
        raise NotImplementedError()

    def finished(self, name, aborted=False, abort_reason=''):
        """Transaction finished.

        name is the name of the transaction.
        aborted indicates if the transaction was
        aborted by some listener.
        abort_reason might contain a str which
        describes why the transaction was aborted.

        """
        raise NotImplementedError()

    def transfer(self, transfer_type, filename):
        """Transfer filename.

        transfer_type is either 'download' or
        'upload'.

        """
        raise NotImplementedError()

    def processed(self, filename, new_state):
        """Operation was performed on file filename.

        new_state is the new state of filename.
        new_state == None indicates that filename was
        removed from the wc.

        """
        raise NotImplementedError()


class TransactionNotifier(object):
    """Notify all transaction listener."""

    def __init__(self, listener):
        super(TransactionNotifier, self).__init__()
        self.listener = listener

    def _notify(self, method, *args, **kwargs):
        rets = []
        for listener in self.listener:
            meth = getattr(listener, method)
            rets.append(meth(*args, **kwargs))
        return rets

    def begin(self, *args, **kwargs):
        """Return True if the transaction can start - otherwise False."""
        rets = self._notify('begin', *args, **kwargs)
        falses = [ret for ret in rets if ret is False]
        return len(falses) == 0

    def finished(self, *args, **kwargs):
        self._notify('finished', *args, **kwargs)

    def transfer(self, *args, **kwargs):
        self._notify('transfer', *args, **kwargs)

    def processed(self, *args, **kwargs):
        self._notify('processed', *args, **kwargs)


class FileConflictError(Exception):
    """Exception raises if an operation can't be executed due to conflicts."""

    def __init__(self, conflicts):
        """Construct a new FileConflictError object.

        conflicts is a list of conflicted files.

        """
        super(FileConflictError, self).__init__()
        self.conflicts = conflicts


class PendingTransactionError(Exception):
    """Raised if a transaction was aborted and no rollback is possible."""

    def __init__(self, name):
        """Constructs a new PendingTransactionError object.

        name is the name of the pending transaction.

        """
        self.name = name


class AbstractTransactionState(object):
    """Abstract base class for all transactions."""

    DIR = '_transaction'
    FILENAME = os.path.join(DIR, 'state')

    def __init__(self, path, **kwargs):
        """Constructs a new AbstractTransactionState object.

        path is the path to the package working copy.

        Keyword arguments:
        **kwargs -- optional, implementation specific, keyword arguments

        """
        super(AbstractTransactionState, self).__init__()
        self._path = path

    @property
    def location(self):
        """Return the path to the transaction dir."""
        raise NotImplementedError()

    @property
    def name(self):
        """Return the name of the transaction."""
        raise NotImplementedError()

    @property
    def state(self):
        """Return the current state of the transaction."""
        raise NotImplementedError()

    @state.setter
    def state(self, new_state):
        """Set transaction state to new_state."""
        raise NotImplementedError()

    @property
    def info(self):
        """Return the info object."""
        raise NotImplementedError()

    @property
    def entrystates(self):
        """Return an entry -> current state mapping."""
        raise NotImplementedError()

    def processed(self, entry, new_state):
        """The entry entry was processed.

        new_state is the new state of the etnry. If new_state
        is None entry won't be tracked anymore. Afterwards
        entry is removed from the info list.
        A ValueError is raised if entry is not part of
        a info list.

        """
        raise NotImplementedError()

    def cleanup(self):
        """Remove transaction (location) dir"""
        raise NotImplementedError()

    @classmethod
    def read_state(cls, path):
        """Tries to read the transaction state.

        path is the path to the package working copy.
        If the state file does not exist None
        is returned. Otherwise an AbstractTransactionState subclass
        instance is returned.

        """

    @staticmethod
    def rollback(path):
        """Revert current transaction (if possible).

        Return True if a rollback is possible (this also
        indicates that the rollback itself was successfull).
        Otherwise False is returned.
        A ValueError is raised if the transaction names/types
        mismatch.

        """
        raise NotImplementedError()


# hmm is a mixin a good idea? or should we do some multiple inheritance
class UpdateStateMixin(object):
    """Provides possible update transaction states."""
    STATE_PREPARE = '1'
    # only local operations are allowed
    STATE_UPDATING = '2'


class CommitStateMixin(object):
    """Provides possible commit transaction states."""
    STATE_TRANSFER = '10'
    # only local operations are allowed
    STATE_COMMITTING = '11'


class WorkingCopy(object):
    """Base class for a working copy."""

    def __init__(self, path, ustate_class, cstate_class,
                 transaction_listener=[],
                 finish_pending_transaction=True):
        """Constructs a new Working copy object.

        path is the path to the working copy. ustate_class is
        the class which is used for an update transaction. cstate_class
        is the class which is used for a commit transaction.

        Keyword arguments:
        transaction_listener -- list of TransactionListeners (default: [])
        finish_pending_transaction -- finish a pending transaction (if
                                      one exists) (default: True)

        """
        super(WorkingCopy, self).__init__()
        self.path = path
        self._ustate_class = ustate_class
        self._cstate_class = cstate_class
        self.notifier = TransactionNotifier(transaction_listener)
        if finish_pending_transaction:
            self.finish_pending_transaction()

    def has_conflicts(self):
        """Check if working copy has conflicted entries.

        Return a list of conflicted entries (empty list
        indicates no conflicts).

        """
        raise NotImplementedError()

    def is_updateable(self, rollback=False):
        """Check if wc can be updated.

        If rollback is True a pending transaction will be
        rolled back (if possible).
        Return True if an update is possible. Otherwise
        False is returned.

        """
        if self.has_conflicts():
            return False
        ustate = self._pending_transaction()
        if ustate is None:
            return True
        elif ustate.name == 'update':
            return True
        elif rollback:
            return self._cstate_class.rollback(self.path)
        return ustate.state == CommitStateMixin.STATE_TRANSFER

    def is_commitable(self, rollback=False):
        """Check if wc can be committed.

        If rollback is True a pending transaction will be
        rolled back (if possible).
        Return True if a commit is possible. Otherwise
        False is returned.

        """
        if self.has_conflicts():
            return False
        cstate = self._pending_transaction()
        if cstate is None:
            return True
        elif cstate.name == 'commit':
            return True
        elif rollback:
            return self._ustate_class.rollback(self.path)
        return cstate.state == UpdateStateMixin.STATE_PREPARE

    def finish_pending_transaction(self):
        """Finish a pending transaction (if one exists).

        Either the transaction is finished or a rollback is
        done.

        """
        state = self._pending_transaction()
        if state is None:
            return
        elif not state.rollback(self.path):
            if state.name == 'commit':
                self.commit()
            elif state.name == 'update':
                self.update()

    def _pending_transaction(self):
        """Return a AbstractTransactionState subclass instance.

        If no pending transaction exists None is returned.

        """
        cstate = self._cstate_class.read_state(self.path)
        if cstate is None:
            return None
        elif cstate.name == 'commit':
            return cstate
        return self._ustate_class.read_state(self.path)

    @no_conflicts
    @no_pending_transaction
    def add(self, entry, *args, **kwargs):
        """Add entry to working copy.

        Afterwards entry is tracked with state 'A'.
        A ValueError is raised if entry does not exist or
        is "invalid" or if it is already tracked.

        Usage of *args and **kwargs is implementation specific.

        """
        pass

    @no_conflicts
    @no_pending_transaction
    def remove(self, entry, *args, **kwargs):
        """Remove entry from the working copy.

        Actually this marks entry for deletion (entry has
        state 'D' afterwards).
        A ValueError is raised if entry is not tracked or
        if entry is conflicted (has state 'C') or if entry
        is skipped (has state 'S').

        Usage of *args and **kwargs is implementation specific.

        """
        pass

    @no_conflicts
    @no_pending_transaction
    def revert(self, entry, *args, **kwargs):
        """Revert an entry.

        A ValueError is raised if a state is not
        allowed (for instance if entry has a specific state).

        Usage of *args and **kwargs is implementation specific.

        """
        pass

    def _transaction_begin(self, name, info):
        """Notify all transaction listener.

        name is the name of the transaction.
        info is the info object.
        Return True if all listener signalled that the
        transaction should start. Otherwise False is
        returned.
        If the transaction will be aborted all listener
        will be notified.

        """
        if not self.notifier.begin(name, info):
            msg = "listener aborted transaction \"%s\"" % name
            self.notifier.finished('update', aborted=True,
                                   abort_reason=msg)
            return False
        return True
