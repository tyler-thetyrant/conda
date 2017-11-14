from __future__ import absolute_import, division, print_function, unicode_literals

from os import listdir
from os.path import basename, isdir, isfile, join
import re
import sys

from .._vendor.auxlib.ish import dals
from ..base.constants import PREFIX_MAGIC_FILE, ROOT_ENV_NAME
from ..base.context import context
from ..models.match_spec import MatchSpec


def confirm(message="Proceed", choices=('yes', 'no'), default='yes'):
    assert default in choices, default
    if context.dry_run:
        from ..exceptions import DryRunExit
        raise DryRunExit()

    options = []
    for option in choices:
        if option == default:
            options.append('[%s]' % option[0])
        else:
            options.append(option[0])
    message = "%s (%s)? " % (message, '/'.join(options))
    choices = {alt: choice
               for choice in choices
               for alt in [choice, choice[0]]}
    choices[''] = default
    while True:
        # raw_input has a bug and prints to stderr, not desirable
        sys.stdout.write(message)
        sys.stdout.flush()
        user_choice = sys.stdin.readline().strip().lower()
        if user_choice not in choices:
            print("Invalid choice: %s" % user_choice)
        else:
            sys.stdout.write("\n")
            sys.stdout.flush()
            return choices[user_choice]


def confirm_yn(message="Proceed", default='yes'):
    if context.dry_run:
        from ..exceptions import DryRunExit
        raise DryRunExit()
    if context.always_yes:
        return True
    try:
        choice = confirm(message=message, choices=('yes', 'no'),
                         default=default)
    except KeyboardInterrupt as e:  # pragma: no cover
        from ..exceptions import CondaSystemExit
        raise CondaSystemExit("\nOperation aborted.  Exiting.", e)
    if choice == 'no':
        from ..exceptions import CondaSystemExit
        raise CondaSystemExit("Exiting.")
    return True


def ensure_name_or_prefix(args, command):
    if not (args.name or args.prefix):
        from ..exceptions import CondaValueError
        raise CondaValueError('either -n NAME or -p PREFIX option required,\n'
                              'try "conda %s -h" for more details' % command)


def arg2spec(arg, json=False, update=False):
    try:
        spec = MatchSpec(arg)
    except:
        from ..exceptions import CondaValueError
        raise CondaValueError('invalid package specification: %s' % arg)

    name = spec.name
    if not spec._is_simple() and update:
        from ..exceptions import CondaValueError
        raise CondaValueError("""version specifications not allowed with 'update'; use
    conda update  %s%s  or
    conda install %s""" % (name, ' ' * (len(arg) - len(name)), arg))

    return str(spec)


def specs_from_args(args, json=False):
    return [arg2spec(arg, json=json) for arg in args]


spec_pat = re.compile(r'''
(?P<name>[^=<>!\s]+)               # package name
\s*                                # ignore spaces
(
  (?P<cc>=[^=]+(=[^=]+)?)          # conda constraint
  |
  (?P<pc>(?:[=!]=|[><]=?).+)       # new (pip-style) constraint(s)
)?
$                                  # end-of-line
''', re.VERBOSE)


def strip_comment(line):
    return line.split('#')[0].rstrip()


def spec_from_line(line):
    m = spec_pat.match(strip_comment(line))
    if m is None:
        return None
    name, cc, pc = (m.group('name').lower(), m.group('cc'), m.group('pc'))
    if cc:
        return name + cc.replace('=', ' ')
    elif pc:
        return name + ' ' + pc.replace(' ', '')
    else:
        return name


def specs_from_url(url, json=False):
    from conda.gateways.connection.download import TmpDownload

    explicit = False
    with TmpDownload(url, verbose=False) as path:
        specs = []
        try:
            for line in open(path):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line == '@EXPLICIT':
                    explicit = True
                if explicit:
                    specs.append(line)
                    continue
                spec = spec_from_line(line)
                if spec is None:
                    from ..exceptions import CondaValueError
                    raise CondaValueError("could not parse '%s' in: %s" %
                                          (line, url))
                specs.append(spec)
        except IOError as e:
            from ..exceptions import CondaFileIOError
            raise CondaFileIOError(path, e)
    return specs


def names_in_specs(names, specs):
    return any(spec.split()[0] in names for spec in specs)


def disp_features(features):
    if features:
        return '[%s]' % ' '.join(features)
    else:
        return ''


def stdout_json(d):
    import json
    from .._vendor.auxlib.entity import EntityEncoder
    json.dump(d, sys.stdout, indent=2, sort_keys=True, cls=EntityEncoder)
    sys.stdout.write('\n')


def stdout_json_success(success=True, **kwargs):
    result = {'success': success}
    result.update(kwargs)
    stdout_json(result)


def list_prefixes():
    # Lists all the prefixes that conda knows about.
    for envs_dir in context.envs_dirs:
        if not isdir(envs_dir):
            continue
        for dn in sorted(listdir(envs_dir)):
            prefix = join(envs_dir, dn)
            if isdir(prefix) and isfile(join(prefix, PREFIX_MAGIC_FILE)):
                prefix = join(envs_dir, dn)
                yield prefix

    yield context.root_prefix


def handle_envs_list(acc, output=True):

    if output:
        print("# conda environments:")
        print("#")

    def disp_env(prefix):
        fmt = '%-20s  %s  %s'
        default = '*' if prefix == context.default_prefix else ' '
        name = (ROOT_ENV_NAME if prefix == context.root_prefix else
                basename(prefix))
        if output:
            print(fmt % (name, default, prefix))

    for prefix in list_prefixes():
        disp_env(prefix)
        if prefix != context.root_prefix:
            acc.append(prefix)

    if output:
        print()


def check_non_admin():
    from ..common.platform import is_admin
    if not context.non_admin_enabled and not is_admin():
        from ..exceptions import OperationNotAllowed
        raise OperationNotAllowed(dals("""
            The create, install, update, and remove operations have been disabled
            on your system for non-privileged users.
        """))
