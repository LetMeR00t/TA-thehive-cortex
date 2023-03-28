from typing import List
import urllib

from thehive4py.endpoints._base import EndpointBase


class FunctionEndpoint(EndpointBase):
    def run(self, function_name: str, input: dict) -> str:
        return self._session.make_request(
            "POST", path="/api/v1/function/"+urllib.parse.quote(function_name), json=input
        )
