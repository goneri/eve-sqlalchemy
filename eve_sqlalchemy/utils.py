# -*- coding: utf-8 -*-

"""
    Helpers and utils functions

    :copyright: (c) 2013 by Andrew Mleczko and Tomasz Jezierski (Tefnet)
    :license: BSD, see LICENSE for more details.

"""

import ast
import collections
import copy
import re

from eve.utils import config
from sqlalchemy.ext.declarative.api import DeclarativeMeta


def dict_update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            if k in d and isinstance(d[k], collections.Mapping):
                dict_update(d[k], v)
            else:
                d[k] = v
        else:
            d[k] = u[k]


def validate_filters(where, resource):
    allowed = config.DOMAIN[resource]['allowed_filters']
    if '*' not in allowed:
        for filt in where:
            key = filt.left.key
            if key not in allowed:
                return "filter on '%s' not allowed" % key
    return None


def lookup_foreign_resource(field, fields, resource):

    foreign_resource = None
    foreign_fields = []
    try:
        data_relation = config.DOMAIN[resource]['schema'][field]['data_relation']
        if data_relation['embeddable']:
            foreign_resource = data_relation['resource']
            foreign_fields = []
            for k in config.DOMAIN[foreign_resource]['schema'].keys():
                if 'data_relation' not in config.DOMAIN[foreign_resource]['schema'][k]:
                    foreign_fields.append(k)
    except KeyError:
        # NOTE(Gonéri): Probably a missing key in the config.DOMAIN structure
        pass
    return foreign_resource, foreign_fields


def sqla_object_to_dict(obj, fields, resource):
    """ Creates a dict containing copies of the requested fields from the
    SQLAlchemy query result """
    if config.LAST_UPDATED not in fields:
        fields.append(config.LAST_UPDATED)
    if config.DATE_CREATED not in fields:
        fields.append(config.DATE_CREATED)
    if config.ETAG not in fields \
            and getattr(config, 'IF_MATCH', True):
        fields.append(config.ETAG)

    result = {}
    for field in fields:
        foreign_resource, foreign_fields = lookup_foreign_resource(
            field, fields, resource)

        try:
            val = obj.__getattribute__(field)

            # If association proxies are embedded, their values must be copied
            # since they are garbage collected when Eve try to encode the
            # response.
            if getattr(val, 'copy', None) is not None:
                val = val.copy()

            # is this field another SQLalchemy object, or a list of SQLalchemy objects?
            if isinstance(val.__class__, DeclarativeMeta):
                if foreign_fields:
                    # we have embedded document in schema, let's resolve it:
                    result[field] = sqla_object_to_dict(val, foreign_fields,
                                                        foreign_resource)
                else:
                    result[field] = getattr(val, config.ID_FIELD)

            elif isinstance(val, list) and len(val) > 0 \
                    and isinstance(val[0].__class__, DeclarativeMeta):
                if foreign_fields:
                    # we have embedded document in schema, let's resolve it:
                    result[field] = [sqla_object_to_dict(x, foreign_fields,
                                                         foreign_resource)
                                     for x in val]
                else:
                    result[field] = [getattr(x, config.ID_FIELD) for x in val]

            else:
                # If integral type, just copy it
                result[field] = copy.copy(val)
        except AttributeError:
            # Ignore if the requested field does not exist
            # (may be wrong embedding parameter)
            pass

    return result


def extract_sort_arg(req):
    if req.sort:
        if re.match('^[-,\w]+$', req.sort):
            arg = []
            for s in req.sort.split(','):
                if s.startswith('-'):
                    arg.append([s[1:], -1])
                else:
                    arg.append([s])
            return arg
        else:
            return ast.literal_eval(req.sort)
    else:
        return None
