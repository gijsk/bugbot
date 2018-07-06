# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
from dateutil.relativedelta import relativedelta
from jinja2 import Environment, FileSystemLoader
from libmozdata.bugzilla import Bugzilla
from libmozdata import utils as lmdutils
from auto_nag import mail, utils
from auto_nag.scripts.common import get_login_info, send_email


# https://bugzilla.mozilla.org/buglist.cgi?resolution=---&resolution=FIXED&resolution=INVALID&resolution=WONTFIX&resolution=DUPLICATE&resolution=WORKSFORME&resolution=INCOMPLETE&resolution=SUPPORT&resolution=EXPIRED&resolution=MOVED&v1=yes&f1=cf_has_regression_range&keywords_type=nowords&keywords=regression%2C%20&o1=equals&query_format=advanced&list_id=14173174
def get_bz_params(date):
    date = lmdutils.get_date_ymd(date)
    lookup = utils.get_config('common', 'days_lookup', 7)
    start_date = date - relativedelta(days=lookup)
    end_date = date + relativedelta(days=1)
    fields = ['id']
    params = {'include_fields': fields,
              'bug_status': ['---', 'FIXED', 'INVALID', 'WONTFIX', 'DUPLICATE', 'WORKSFORME', 'INCOMPLETE', 'SUPPORT', 'EXPIRED', 'MOVED'],
              'f1': 'keywords',
              'o1': 'nowords',
              'v1': 'regression',
              'f2': 'resolution',
              'o2': 'changedafter',
              'v2': start_date,
              'f3': 'resolution',
              'o3': 'changedbefore',
              'v3': end_date,
              'f4': 'cf_has_regression_range',
              'o4': 'equals',
              'v4': 'yes'
              }

    return params


def get_bugs(date='today'):
    # the search query can be long to evaluate
    TIMEOUT = 240

    def bug_handler(bug, data):
        data.append(bug['id'])

    bugids = []
    Bugzilla(get_bz_params(date),
             bughandler=bug_handler,
             bugdata=bugids,
             timeout=TIMEOUT).get_data().wait()

    return sorted(bugids)


def autofix(bugs):
    bugs = list(map(str, bugs))
    Bugzilla(bugs).put({
        'keywords': {
            'add': ['regression']
            }
        })

    return bugs


def get_email(bztoken, date, template, title, dryrun, bug_ids=[]):
    Bugzilla.TOKEN = bztoken
    bugids = get_bugs(date=date)
    if not dryrun:
        bugids = autofix(bugids)
    if bugids:
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template(template)
        body = template.render(date=date,
                               bugids=bugids)
        title = title.format(date)
        return title, body
    return None, None


if __name__ == '__main__':
    description = 'Get the closed bugs with has-regression-range without the regression keyword'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-d', '--dryrun', dest='dryrun',
                        action='store_true', default=False,
                        help='Just do the query, and print emails to console without emailing anyone') # NOQA
    parser.add_argument('-D', '--date', dest='date',
                        action='store', default='today',
                        help='Date for the query')
    args = parser.parse_args()

    login_info = get_login_info()
    date = lmdutils.get_date(args.date)
    template='has_reg_range_email.html'
    subject='[autonag] Bugs with has_regression_range=yes but no regression keyword {}'
    title, body = get_email(login_info['bz_api_key'], date, template, subject, dryrun=args.dryrun)

    send_email(category="HAS_REG_RANGE", date=date, template=template , title=title, dryrun=args.dryrun)
