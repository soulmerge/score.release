#!/usr/bin/python3

# Copyright © 2015,2016 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

import re
import subprocess
import os
import click
from glob import glob


here = os.path.dirname(__file__)


def read_current_version(repo):
    if repo.startswith('py.'):
        content = open('setup.py').read()
        lines = content.split('\n')
        line = next(l for l in lines if 'version=' in l)
        return re.sub(r'^[^=]+=.([0-9.]+).*$', r'\1', line)
    else:
        content = open('package.json').read()
        lines = content.split('\n')
        line = next(l for l in lines if '"version": ' in l)
        return re.sub(r'^[^:]+:.*?([0-9.]+).*$', r'\1', line)


def increment_version(version):
    parts = version.split('.')
    newparts = parts[:]
    if len(newparts) == 2:
        newparts.append(1)
    else:
        newparts[-1] = 1 + int(newparts[-1])
    return '.'.join(map(str, newparts))


def replace_version_string(file, regex, new):
    content = open(file).read()
    match = regex.search(content)
    if match:
        line = match.group(1) + new + match.group(3)
        content = content.replace(match.group(0), line)
        open(file, 'w').write(content)


pyversion_regex = r'''^(__version__ = ["'])(\d+\.\d+(?:\.\d+)?)(["'])$'''
jsversion_regex = \
    r'''^(\s*(?:[a-zA-Z_]+\.__version__\s+=|["']?__version__["']?\s*:)''' \
    r'''\s+["'])(\d+\.\d+(?:\.\d+)?)(["'][,;])$'''


def update_repo_version(repo, old, new):
    if repo.startswith('py.'):
        file = 'setup.py'
        regex = re.compile(pyversion_regex, re.MULTILINE)
    else:
        file = 'package.json'
        regex = re.compile(jsversion_regex, re.MULTILINE)
    content = open(file).read()
    content = content.replace(old, new, 1)
    open(file, 'w').write(content)
    if repo.startswith('py.'):
        for (dirpath, dirnames, filenames) in os.walk('score'):
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue
                file = os.path.join(dirpath, filename)
                replace_version_string(file, regex, new)
    else:
        for file in glob('*.js'):
            replace_version_string(file, regex, new)


def publish(repo, old, new):
    subprocess.check_call(
        ['git', 'commit', '-m', 'Release: %s' % new, '--all'])
    subprocess.check_call(['git', 'tag', new])
    subprocess.check_call(['git', 'push', '--all'])
    subprocess.check_call(['git', 'push', '--tags'])
    if repo.startswith('py.'):
        subprocess.check_call(['python', 'setup.py', 'sdist', 'upload'])
    else:
        subprocess.check_call(['npm', 'publish'])


def check_new_version(repo, old, new):
    old_parts = old.split('.')
    new_parts = new.split('.')
    incremented = False
    for i, new_part in enumerate(new_parts):
        try:
            old_part = old_parts[i]
        except KeyError:
            return True
        if new_part == old_part:
            continue
        if incremented:
            if new_part != '0':
                return False
        elif int(new_part) == int(old_part) + 1:
            incremented = True
        else:
            return False
    return True


def repo_is_dirty():
    return subprocess.call(['git', 'diff-index', '--quiet', 'HEAD', '--'])


@click.command()
@click.option('-v', '--version', 'version')
@click.option('-p', '--pretend', is_flag=True, default=False)
@click.argument('repository', type=click.Path(file_okay=False, dir_okay=True))
def main(repository, version=None, pretend=False):
    assert repository.startswith('py.') or repository.startswith('js.')
    os.chdir(os.path.join(here, repository))
    old_version = read_current_version(repository)
    if version is None:
        version = increment_version(old_version)
    elif not re.match(r'^[0-9]+\.[0-9]+\.[0-9]+$', version):
        raise click.ClickException(
            'Invalid version number (must match `\d+.\d+.\d+`)')
    else:
        if not check_new_version(repository, old_version, version):
            click.confirm(
                'Not a logical increment: %s -> %s\ncontinue anyway?' %
                (old_version, version), abort=True)
    if pretend:
        print('Would release %s as %s (current=%s)' % (
            repository, version, old_version))
        return
    if repo_is_dirty():
        raise click.ClickException('Repository contains uncommited changes')
    print(old_version, '->', version)
    update_repo_version(repository, old_version, version)
    publish(repository, old_version, version)


if __name__ == '__main__':
    main()
