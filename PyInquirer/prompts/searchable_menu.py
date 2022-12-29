# -*- coding: utf-8 -*-
"""
`searchable_menu` type question (based on the `list` type)
"""
from prompt_toolkit.application import Application, get_app
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.filters import IsDone
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout import Layout
from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import Condition

from . import PromptParameterException
from ..separator import Separator
from .common import if_mousedown, default_style

# custom control based on FormattedTextControl
# docu here:
# https://github.com/jonathanslenders/python-prompt-toolkit/issues/281
# https://github.com/jonathanslenders/python-prompt-toolkit/blob/master/examples/full-screen-layout.py
# https://github.com/jonathanslenders/python-prompt-toolkit/blob/master/docs/pages/full_screen_apps.rst


class InquirerControl(FormattedTextControl):

    def __init__(self, choices, default, **kwargs):
        self.selected_option_index = 0
        self.answered = False
        self.choices_all = choices
        self.search_string = ""
        self.default = default
        self._init_choices()
        super().__init__(self._get_choice_tokens, **kwargs)

    def _init_choices(self):
        n_rows_to_show = 10

        self.choices = []  # list (name, value, disabled)
        if self.search_string != "":
            choices = self._filter_choices()
        else:
            choices = self.choices_all

        if len(choices) == 0:
            self.choices.append(("No matching choices found", "no_matches", True))
            self.selected_option_index = 0
            return

        default_choice_selected = False
        for i, c in enumerate(choices[:n_rows_to_show]):
            if isinstance(c, str):
                self.choices.append((c, c, None))
            else:
                name = c.get('name')
                value = c.get('value', name)
                disabled = c.get('disabled', None)
                self.choices.append((name, value, disabled))
                if value == self.default:
                    self.selected_option_index = i
            if self.default and (self.default in [i, c]):
                self.selected_option_index = i  # default choice exists
                default_choice_selected = True
        if not default_choice_selected:
            self.selected_option_index = 0

    def _filter_choices(self):
        def _is_match(choice, pattern):
            if isinstance(choice, str):
                return pattern in choice
            return pattern in choice["name_for_search"]

        choices_filtered = [choice for choice in self.choices_all if _is_match(
            choice, self.search_string)]
        return choices_filtered

    @property
    def choice_count(self):
        return len(self.choices)

    def _get_choice_tokens(self):
        tokens = []

        def append(index, choice):
            selected = (index == self.selected_option_index)

            @if_mousedown
            def select_item(mouse_event):
                # bind option with this index to mouse event
                self.selected_option_index = index
                self.answered = True
                get_app().exit(result=self.get_selection()[0])

            if isinstance(choice[0], Separator):
                tokens.append(('class:separator', '  %s\n' % choice[0]))
            else:
                tokens.append(('class:pointer' if selected else '', ' \u276f ' if selected
                               else '   '))
                if selected:
                    tokens.append(('[SetCursorPosition]', ''))
                if choice[2]:  # disabled
                    tokens.append(
                        ('class:Selected' if selected else '',
                         '- %s' % choice[0]))
                else:
                    try:
                        tokens.append(('class:Selected' if selected else '', str(choice[0]),
                                       select_item))
                    except:
                        tokens.append(('class:Selected' if selected else '', choice[0],
                                       select_item))
                tokens.append(('', '\n'))

        # prepare the select choices
        for i, choice in enumerate(self.choices):
            append(i, choice)
        tokens.pop()  # Remove last newline.
        return tokens

    def get_selection(self):
        return self.choices[self.selected_option_index]


def question(message, **kwargs):
    # TODO disabled, dict choices
    if not 'choices' in kwargs:
        raise PromptParameterException('choices')

    choices = kwargs.pop('choices', None)
    default = kwargs.pop('default', None)
    qmark = kwargs.pop('qmark', '?')
    # TODO style defaults on detail level
    style = kwargs.pop('style', default_style)

    ic = InquirerControl(choices, default=default)

    def get_prompt_tokens():
        tokens = []

        tokens.append(('class:questionmark', qmark))
        tokens.append(('class:question', ' %s ' % message))
        if ic.answered:
            tokens.append(('class:answer', ' ' + ic.get_selection()[0]))
        else:
            tokens.append(('class:instruction', ' (Use arrow keys)'))
            tokens.append(('class:answer', ' ' + ic.search_string))  # show search term
        return tokens

    @Condition
    def has_been_properly_answered():
        return (not ic.answered) or ic.selected_option_index != -1

    # assemble layout
    layout = HSplit([
        ConditionalContainer(
            Window(height=D.exact(1), content=FormattedTextControl(get_prompt_tokens)),
            # to show the question after it's been answered only if a legit answer was
            # provided -- not if the question was cancelled
            filter=has_been_properly_answered),
        ConditionalContainer(
            Window(ic),
            filter=~IsDone()
        )
    ])

    # key bindings
    kb = KeyBindings()

    @kb.add('c-q', eager=True)
    @kb.add('c-c', eager=True)
    def _(event):
        raise KeyboardInterrupt()

    @kb.add("escape", eager=True)
    def cancel(event):
        ic.answered = True
        ic.selected_option_index = -1
        event.app.exit(result=None)

    @kb.add('down', eager=True)
    def move_cursor_down(event):

        def _next():
            ic.selected_option_index = (
                (ic.selected_option_index + 1) % ic.choice_count)
        _next()
        while isinstance(ic.choices[ic.selected_option_index][0], Separator) or\
                ic.choices[ic.selected_option_index][2]:
            _next()

    @kb.add('up', eager=True)
    def move_cursor_up(event):
        def _prev():
            ic.selected_option_index = (
                (ic.selected_option_index - 1) % ic.choice_count)
        _prev()
        while isinstance(ic.choices[ic.selected_option_index][0], Separator) or \
                ic.choices[ic.selected_option_index][2]:
            _prev()

    @kb.add('enter', eager=True)
    def set_answer(event):
        if not ic.get_selection()[2]:  # if not disabled
            ic.answered = True
            event.app.exit(result=ic.get_selection()[1])

    @kb.add('a', eager=True)
    @kb.add('b', eager=True)
    @kb.add('c', eager=True)
    @kb.add('d', eager=True)
    @kb.add('e', eager=True)
    @kb.add('f', eager=True)
    @kb.add('g', eager=True)
    @kb.add('h', eager=True)
    @kb.add('i', eager=True)
    @kb.add('j', eager=True)
    @kb.add('k', eager=True)
    @kb.add('l', eager=True)
    @kb.add('m', eager=True)
    @kb.add('n', eager=True)
    @kb.add('o', eager=True)
    @kb.add('p', eager=True)
    @kb.add('q', eager=True)
    @kb.add('r', eager=True)
    @kb.add('s', eager=True)
    @kb.add('t', eager=True)
    @kb.add('u', eager=True)
    @kb.add('v', eager=True)
    @kb.add('w', eager=True)
    @kb.add('x', eager=True)
    @kb.add('y', eager=True)
    @kb.add('z', eager=True)
    @kb.add(' ', eager=True)
    @kb.add('backspace', eager=True)
    def filter_options(event):
        letter = event.key_sequence[0].key
        if letter == Keys.ControlH:  # backspace
            if len(ic.search_string) > 0:
                ic.search_string = ic.search_string[:-1]
        else:  # ordinary letters
            ic.search_string += letter

        ic.selected_option_index = 0
        ic.reset()
        ic._init_choices()

    return Application(
        layout=Layout(layout),
        key_bindings=kb,
        mouse_support=True,
        style=style
    )
