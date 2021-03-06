#!/usr/bin/env python

import itertools
import os

from string import Template

import yaml

import ansibullbot.constants as C


class BotMetadataParser(object):

    @staticmethod
    def parse_yaml(data):

        def clean_list_items(inlist):
            if isinstance(inlist, list):
                inlist = str(inlist)
            if '&' in inlist:
                if C.DEFAULT_BREAKPOINTS:
                    logging.error('breakpoint!')
                    import epdb; epdb.st()
            inlist = inlist.replace("[", '')
            inlist = inlist.replace("]", '')
            inlist = inlist.replace("'", '')
            inlist = inlist.replace(",", '')
            inlist = inlist.split()
            return inlist

        def fix_lists(data):
            for k, v in data['files'].items():
                if v is None:
                    continue

                for k2, v2 in v.items():
                    if isinstance(v2, str) and '$' in v2:
                        tmpl = Template(v2)
                        newv2 = tmpl.substitute(**data['macros'])
                        newv2 = clean_list_items(newv2)
                        data['files'][k][k2] = newv2
                        v2 = newv2
                    if isinstance(v2, (str, unicode)):
                        data['files'][k][k2] = v2.split()

            return data

        def fix_keys(data):
            replace = []
            for k in data['files'].keys():
                if '$' in k:
                    replace.append(k)
            for x in replace:
                tmpl = Template(x)
                newkey = tmpl.substitute(**data['macros'])
                data['files'][newkey] = data['files'][x]
                data['files'].pop(x, None)

            paths = data['files'].keys()
            for p in paths:
                normpath = os.path.normpath(p)
                if p != normpath:
                    metadata = data['files'].pop(p)
                    data['files'][normpath] = metadata
            return data

        def extend_labels(data):
            for k, v in data['files'].items():
                # labels from path(s)
                if v is None:
                    continue
                labels = v.get('labels', [])
                if isinstance(labels, str):
                    labels = labels.split()
                    labels = [x.strip() for x in labels if x.strip()]
                path_labels = [x.strip() for x in k.split('/') if x.strip()]
                for x in path_labels:
                    x = x.replace('.py', '')
                    x = x.replace('.ps1', '')
                    if x not in labels:
                        labels.append(x)
                data['files'][k]['labels'] = sorted(set(labels))

            return data

        def fix_teams(data):
            for k, v in data['macros'].items():
                if v is None:
                    continue
                if not k.startswith('team_') or isinstance(v, list):
                    continue
                names = v.split()
                data['macros'][k] = names
            return data

        def _propagate(files, top, child, field):
            '''Copy key named 'field' from top to child'''
            top_entries = files[top].get(field, [])
            if top_entries:
                if field not in files[child]:
                    files[child][field] = []

                field_keys = '%s_keys' % field
                if field_keys not in files[child]:
                    files[child][field_keys] = []
                files[child][field_keys].append(top)

                for entry in top_entries:
                    if entry not in files[child][field]:
                        files[child][field].append(entry)

        def propagate_keys(data):
            files = data['files']
            '''maintainers and ignored keys defined at a directory level are copied to subpath'''
            for file1, file2 in itertools.combinations(files.keys(), 2):
                # Python 2.7 doesn't provide os.path.commonpath
                common = os.path.commonprefix([file1, file2])
                top = min(file1, file2)
                child = max(file1, file2)

                top_components = top.split('/')
                child_components = child.split('/')

                if common == top and top_components == child_components[:len(top_components)]:
                    _propagate(files, top, child, 'maintainers')
                    _propagate(files, top, child, 'ignored')

        #################################
        #   PARSE
        #################################

        ydata = yaml.load(data)

        # fix the team macros
        ydata = fix_teams(ydata)

        # fix the macro'ized file keys
        ydata = fix_keys(ydata)

        for k, v in ydata['files'].items():
            if v is None:
                # convert empty val in dict
                ydata['files'][k] = {}
            elif isinstance(v, (str, unicode)):
                # convert string vals to a maintainers key in a dict
                ydata['files'][k] = {
                    'maintainers': v
                }

            ydata['files'][k]['maintainers_keys'] = [k]

        # replace macros in files section
        ydata = fix_lists(ydata)

        # extend labels by filepath
        ydata = extend_labels(ydata)

        propagate_keys(ydata)

        return ydata
