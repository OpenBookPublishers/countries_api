#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Countries JSON API. Simple web.py based API to a
PostgreSQL database that runs on port 8080.

usage: python api.py

(c) Javier Arias, Open Book Publishers, October 2018
Use of this software is governed by the terms of the MIT license

Dependencies:
  PyJWT==1.6.1
  psycopg2-binary==2.7.5
  web.py==0.39
"""

import os
import web
import jwt
import json
from aux import logger_instance, debug_mode
from errors import Error, internal_error, not_found, FATAL, NORESULT, \
    FORBIDDEN, UNAUTHORIZED, BADFILTERS

# get logging interface
logger = logger_instance(__name__)
web.config.debug = debug_mode()
# Get authentication configuration
SECRET_KEY = os.environ['SECRET_KEY']
# Define routes
urls = (
    "/countries(/?)", "countriesctrl.CountryController",
    "/names(/?)", "countrynamesctrl.CountrynameController"
)

try:
    db = web.database(dbn='postgres',
                      host=os.environ['DB_HOST'],
                      user=os.environ['DB_USER'],
                      pw=os.environ['DB_PASS'],
                      db=os.environ['DB_DB'])
except Exception as error:
    logger.error(error)
    raise Error(FATAL)


def api_response(fn):
    """Decorator to provided consistency in all responses"""
    def response(self, *args, **kw):
        data  = fn(self, *args, **kw)
        count = len(data)
        if count > 0:
            return {'status': 'ok', 'code': 200, 'count': count, 'data': data}
        else:
            raise Error(NORESULT)
    return response


def json_response(fn):
    """JSON decorator"""
    def response(self, *args, **kw):
        web.header('Content-Type', 'application/json;charset=UTF-8')
        web.header('Access-Control-Allow-Origin',
                   '"'.join([os.environ['ALLOW_ORIGIN']]))
        web.header('Access-Control-Allow-Credentials', 'true')
        web.header('Access-Control-Allow-Headers',
                   'Authorization, x-test-header, Origin, '
                   'X-Requested-With, Content-Type, Accept')
        return json.dumps(fn(self, *args, **kw), ensure_ascii=False)
    return response


def check_token(fn):
    """Decorator to act as middleware, checking entication token"""
    def response(self, *args, **kw):
        intoken = get_token_from_header()
        try:
            jwt.decode(intoken, SECRET_KEY)
        except jwt.exceptions.DecodeError:
            raise Error(FORBIDDEN)
        except jwt.ExpiredSignatureError:
            raise Error(UNAUTHORIZED, msg="Signature expired.")
        except jwt.InvalidTokenError:
            raise Error(UNAUTHORIZED, msg="Invalid token.")
        return fn(self, *args, **kw)
    return response


def get_token_from_header():
    bearer = web.ctx.env.get('HTTP_AUTHORIZATION')
    return bearer.replace("Bearer ", "") if bearer else ""


def build_params(filters):
    if not filters:
        return "", {}
    params    = filters.split(',')
    options   = {}
    con_codes = []
    con_names = []
    clause    = ""
    for p in params:
        try:
            field, val = p.split(':', 1)
            if field == "continent_name":
                con_names.append(val)
            elif field == "continent_code":
                con_codes.append(val)
            else:
                raise Error(BADFILTERS)
        except BaseException:
            raise Error(BADFILTERS, msg="Unknown filter '%s'" % (p))

    process = {"continent_code": con_codes, "continent_name": con_names}
    for key, values in process.items():
        if len(values) > 0:
            try:
                andclause, ops = build_clause(key, values)
                options.update(ops)
                clause = clause + andclause
            except BaseException:
                raise Error(BADFILTERS)

    return clause, options


def build_clause(attribute, values):
    params = {}
    clause = " AND " + attribute + " IN ("
    no = 1
    for v in values:
        params[attribute + str(no)] = v
        if no > 1:
            clause += ","
        clause += "$" + attribute + str(no)
        no += 1
    return [clause + ")", params]


import countriesctrl  # noqa: F401
import countrynamesctrl  # noqa: F401

if __name__ == "__main__":
    logger.info("Starting API...")
    app = web.application(urls, globals())
    app.internalerror = internal_error
    app.notfound = not_found
    app.run()
