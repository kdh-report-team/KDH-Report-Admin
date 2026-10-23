import os,sys,unittest,json
from pathlib import Path
from unittest.mock import patch
root=Path(r'D:/KDH-Report-All/KDH-Report-Admin');sys.path[:0]=[str(root),str(root/'tests')]
original=Path.read_text
def safe_read(path,*args,**kwargs):
 return '' if path.resolve()==(root/'.env').resolve() else original(path,*args,**kwargs)
with patch.object(Path,'read_text',safe_read),patch.dict(os.environ,{'DATABASE_URL':'','TEST_DATABASE_URL':'','META_CLIENT_ID':'client_kinderhealth','META_REPORTING_ALLOW_PRIMARY_CLIENT':'0'}):
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(root/'tests')))
 Path(r'C:/Users/Admin/AppData/Local/Temp/KDH-FB-Tonight-20261021-offline-result.json').write_text(json.dumps({'run':result.testsRun,'fail':len(result.failures),'error':len(result.errors),'skipped':[(t.id(),reason) for t,reason in result.skipped]}))
 sys.exit(not result.wasSuccessful())
