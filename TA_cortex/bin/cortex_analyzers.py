# encoding = utf-8
from __future__ import print_function
import sys
import traceback
from lib3.cortex4py.api import Api
import splunk.Intersplunk

# This function is used to write any error in the search.log
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def execute():
  try:
    results = []
    api = Api('http://192.168.1.94:9001', '+baoovL+Ned/jzFJxOof9ufvWWAAbLo+')

    analyzers = api.analyzers.find_all({}, range='all')

    # Display enabled analyzers' names
    for analyzer in analyzers:
        results.append({"analyzer": analyzer.name, "description": analyzer.description, "dataTypeAllowed": ";".join(analyzer.dataTypeList)})

    # return the results 
    splunk.Intersplunk.outputResults(results)

  except Exception as e:
      tb = traceback.format_exc()
      eprint("Error on cortex.py: "+str(e)+" - "+str(tb))
 
if __name__ == '__main__':
    execute()
