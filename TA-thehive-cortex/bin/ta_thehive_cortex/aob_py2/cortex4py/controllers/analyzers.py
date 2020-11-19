import os

import json

from cortex4py.query import *
from .abstract import AbstractController
from ..models import Analyzer, Job, AnalyzerDefinition


class AnalyzersController(AbstractController):
    def __init__(self, api):
        AbstractController.__init__(self, 'analyzer', api)

    def find_all(self, query, **kwargs):
        return self._wrap(self._find_all(query, **kwargs), Analyzer)

    def find_one_by(self, query, **kwargs):
        return self._wrap(self._find_one_by(query, **kwargs), Analyzer)

    def get_by_id(self, analyzer_id):
        return self._wrap(self._get_by_id(analyzer_id), Analyzer)

    def get_by_name(self, name):
        return self._wrap(self._find_one_by(Eq('name', name)), Analyzer)

    def get_by_type(self, data_type):
        return self._wrap(self._api.do_get('analyzer/type/{}'.format(data_type)).json(), Analyzer)

    def definitions(self):
        return self._wrap(self._api.do_get('analyzerdefinition').json(), AnalyzerDefinition)

    def enable(self, analyzer_name, config):
        url = 'organization/analyzer/{}'.format(analyzer_name)
        config['name'] = analyzer_name

        return self._wrap(self._api.do_post(url, config).json(), Analyzer)

    def update(self, analyzer_id, config):
        url = 'analyzer/{}'.format(analyzer_id)
        config.pop('name', None)

        return self._wrap(self._api.do_patch(url, config).json(), Analyzer)

    def disable(self, analyzer_id):
        return self._api.do_delete('analyzer/{}'.format(analyzer_id))

    def run_by_id(self, analyzer_id, observable, **kwargs):
        tlp = observable.get('tlp', 2)
        pap = observable.get('pap', 2)
        data_type = observable.get('dataType', None)

        post = {
            'dataType': data_type,
            'tlp': tlp,
            'pap': pap
        }

        params = {}
        if 'force' in kwargs:
            params['force'] = kwargs.get('force', 1)

        # add additional details
        for key in ['message', 'parameters']:
            if key in observable:
                post[key] = observable.get(key, None)

        if observable.get('dataType') == "file":
            file_path = observable.get('data', None)

            file_def = {
                "data": (os.path.basename(file_path), open(file_path, 'rb'),
                         None)
            }

            data = {
                '_json': json.dumps(post)
            }

            return self._wrap(self._api.do_file_post('analyzer/{}/run'.format(analyzer_id), data,
                                                     files=file_def, params=params).json(), Job)
        else:
            post['data'] = observable.get('data')

            return self._wrap(self._api.do_post('analyzer/{}/run'.format(analyzer_id), post, params).json(), Job)

    def run_by_name(self, analyzer_name, observable, **kwargs):
        analyzer = self.get_by_name(analyzer_name)

        return self.run_by_id(analyzer.id, observable, **kwargs)
