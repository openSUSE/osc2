"""Provides an abstract base class for an interactive shell."""

import readline
import subprocess

from osc2.cli import parse
from osc2.cli.description import build_description, build_command


class ShellSyntaxError(SyntaxError):
    """Represents a shell syntax error."""
    pass


class AbstractShell(object):
    """Represents an abstract base class for a shell."""

    def __init__(self, renderer, clear='clear', complete=True):
        """Constructs a new AbstractShell object.

        renderer is a renderer.

        Keyword arguments:
        clear -- path to the clear binary (default: 'clear')
        complete -- if True root commands can be tab-completed (default: True)

        """
        self._renderer = renderer
        self._clear = clear
        self._complete = complete
        self._setup_completion()

    def _setup_completion(self):
        """Setup tab completion."""
        if self._complete:
            readline.set_completer(self.complete)
            readline.parse_and_bind('tab: complete')

    def complete(self, text, state):
        """Acts as a readline completer function.

        Completion only works for top level commands (adding
        completion for subcommands is probably a bit more work).

        """
        root_cls = self._root_cmd_cls()
        cmd_cls = root_cls.cls_map()[root_cls.__name__]
        matches = [cls.cmd for cls in cmd_cls if cls.cmd.startswith(text)]
        match = None
        try:
            match = matches[state]
        except IndexError:
            pass
        return match

    def _check_input(self, inp):
        """Checks user input for syntax errors.

        inp is the user input. In case of a syntax error
        a SyntaxError is raised.

        """
        cnt = 0
        for i in xrange(len(inp)):
            if inp[i] != '"':
                continue
            cnt += 1
            if i == 0 or i == len(inp) - 1:
                continue
            if (cnt % 2 == 0 and inp[i + 1] != ' '
                    or cnt % 2 == 1 and inp[i - 1] != ' '):
                msg = "invalid user input: %s (wrong quoting)" % inp
                raise ShellSyntaxError(msg)
        return cnt % 2 == 0

    def _split_input(self, inp):
        """Returns the whitespace splitted user input.

        Additionally quoted text is interpreted as a single
        element.

        """
        l = inp.split(' ')
        data = []
        while l:
            cur = l.pop(0)
            if cur.startswith('"') and not cur.endswith('"'):
                tmp = [cur]
                while l and not cur.endswith('"'):
                    cur = l.pop(0)
                    tmp.append(cur)
                data.append(' '.join(tmp).strip('"'))
            else:
                data.append(cur.strip('"'))
        return data

    def prompt(self, text='', prompt='> '):
        """Returns the str entered by the user.

        Keyword arguments:
        text -- print text before prompting for input (default: '')
        prompt -- specify a prompt (default: '> ')

        """
        if text:
            self._renderer.render_text(text)
        inp = raw_input(prompt)
        self._check_input(inp)
        while not self._check_input(inp):
            inp += "\n" + raw_input()
        return inp

    def render(self, *args, **kwargs):
        """Displays data to the user.

        It simply delegates the render call to
        the renderer object.

        """
        self._renderer.render(*args, **kwargs)

    def clear(self):
        """Clears the terminal screen."""
        subprocess.call([self._clear], shell=False)

    def _execute(self, inp):
        """Executes user specified command.

        inp is the user input.
        The return value of the executed function/method is
        returned.

        """
        args = self._split_input(inp)
        info = parse.parse(self._root_cmd_cls(), args)
        self._augment_info(info)
        try:
            return info.func(info)
        finally:
            # setup completion again because another shell
            # might have been executed
            self._setup_completion()

    def _augment_info(self, info):
        """Adds or modifies the info object.

        info is a osc2.oscargs.ResolvedInfo instance which
        is returned by the parse.parse method.
        Subclasses may override this method.

        """
        info.set('shell', self)

    def _root_cmd_cls(self):
        """Returns the root command class.

        The root command class is used to initialize the
        argument parser.

        """
        raise NotImplementedError()

    def run(self, *args, **kwargs):
        """Runs the shell with the specified args and kwargs."""
        raise NotImplementedError()


class AbstractItemStorage(object):
    """Represents a storage for multiple items.

    Each item has an associated key. The str representation of
    the key must not contain a whitespace.

    """

    def iteritems(self):
        """Yields (key, item) tuples."""
        raise NotImplementedError()

    def __iter__(self):
        raise NotImplementedError()

    def __str__(self):
        """Returns the str representation of the item storage."""
        return super(AbstractItemStorage, self).__str__()


class HomogenousRenderableItemStorage(AbstractItemStorage):
    """Uses a renderer in order to retrieve the str repr of the items.

    It is required that the items are "homogenous" that is it should
    be possible to retrieve their str repr with the help of a single
    template.

    """

    def __init__(self, renderer, storage_template, item_template, **items):
        """Constructs a new HomogenousRenderableItemStorage object.

        renderer is a renderer object. storage_template is the template
        which is used to retrieve the str repr of the whole item storage.
        item_template is the template which is used to retrieve the
        str repr of a single item.
        **items maps a key to an item.

        """
        super(HomogenousRenderableItemStorage, self).__init__()
        self._renderer = renderer
        self._storage_template = storage_template
        self._items = dict(((k, RenderableItem(renderer, item_template, v))
                            for k, v in items.iteritems()))

    def iteritems(self):
        return self._items.iteritems()

    def __iter__(self):
        return self._items.__iter__()

    def __str__(self):
        return self._renderer.render_only(self._storage_template,
                                          items=self._items)


class RenderableItem(object):
    """Uses a renderer in order to retrieve the str repr of the item."""

    def __init__(self, renderer, item_template, item):
        """Constructs a new RenderableItem object.

        renderer is a renderer object. item_template is the template
        which is used to retrieve the str repr of the item. item is
        the item which should be rendered.

        """
        super(RenderableItem, self).__init__()
        self._renderer = renderer
        self._item_template = item_template
        self.item = item

    def __str__(self):
        return self._renderer.render_only(self._item_template, item=self.item)


class ItemSelector(AbstractShell):
    """Represents an item selector.

    An item selector can be used to select one out of multiple
    items. It will prompt for an input and the item which corresponds
    to the input will be returned.

    """

    def __init__(self, item_storage, **kwargs):
        """Constructs a new ItemSelector object.

        item_storage is subclass instance of AbstractItemStorage.
        The str representation of each key must not contain a
        whitespace character otherwise a ValueError is raised.
        **kwargs are passed to the base class' __init__ method.

        """
        super(ItemSelector, self).__init__(**kwargs)
        for k in item_storage:
            if ' ' in str(k):
                msg = "Key \"%s\" contains an illegal whitespace" % k
                raise ValueError(msg)
        self._item_storage = item_storage
        self._build_cmds(item_storage)

    def _build_cmds(self, item_storage):
        """Builds a command hierarchy for the items."""
        description_cls = build_description('ItemSelector', {})
        self._root_cmd = build_command(description_cls)
        for cmd, item in item_storage.iteritems():
            attrs = {'cmd': cmd,
                     'help_str': str(item),
                     'func': staticmethod(lambda info: item)}
            cls = build_command(description_cls, self._root_cmd, **attrs)

    def _root_cmd_cls(self):
        return self._root_cmd

    def run(self):
        """Runs the item selector"""
        text = str(self._item_storage)
        while True:
            try:
                inp = self.prompt(text=text)
                text = ''
                return self._execute(inp)
            except SystemExit:
                # argparse automatically exits when the
                # help is requested
                pass
            except ShellSyntaxError as e:
                self._renderer.render_text(str(e))
            except KeyboardInterrupt as e:
                msg = "Press to ctrl-D to exit"
                self._renderer.render_text(msg)


class AbstractItemSelectorFactory(object):
    """Factory which can be to create an ItemSelector instance.

    Its main purpose is to abstract from the creation of the
    item storage etc.

    """

    def create(self, items, **kwargs):
        """Returns a new ItemSelector (or subclass) instance.

        items is a dict of items.
        **kwargs are additional arguments for the item storage
        or item selector.

        """
        raise NotImplementedError()


class TransparentRenderableItemSelectorFactory(AbstractItemSelectorFactory):
    """Can be used to create a transparent ItemSelector."""

    def create(self, items, renderer, storage_template, item_template):
        """Returns an ItemSelector subclass instance."""
        class TransparentItemSelector(ItemSelector):
            def run(self):
                return super(TransparentItemSelector, self).run().item

        item_storage = HomogenousRenderableItemStorage(renderer,
                                                       storage_template,
                                                       item_template,
                                                       **items)
        return TransparentItemSelector(item_storage, renderer=renderer)
