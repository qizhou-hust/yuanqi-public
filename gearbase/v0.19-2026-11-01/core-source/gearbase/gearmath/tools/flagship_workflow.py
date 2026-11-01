"""Read-only explicit requirement -> original Stage0 flagship -> verification."""
import copy,hashlib,json
from ..gear import flagship_h2 as H2, flagship_w2w as W2W, flagship_p2 as P2
MODELS={'H2':H2,'W2W':W2W,'P2':P2}

def requirement_sha256(req):
    return hashlib.sha256(json.dumps(req,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def requirement_schema():
    return {'type':'object','additionalProperties':False,'required':['family','scope','parameters','source'],
            'properties':{'family':{'type':'string','enum':list(MODELS)},'scope':{'type':'string','enum':['stage0']},
                          'parameters':{'type':'object'},'source':{'type':'string','minLength':1}}}

def _blocked(status,message):return {'status':status,'errors':[{'code':status,'message':message}],'engineering_accepted':False}

def compile_requirement(req):
    if not isinstance(req,dict) or set(req)-{'family','scope','parameters','source'}:return _blocked('blocked_invalid_inputs','Only explicit Stage0 requirement fields are accepted')
    if req.get('scope')!='stage0':return _blocked('blocked_unsupported_scope','Explicit Stage0 scope required; full family rating is unavailable')
    family=req.get('family')
    if not isinstance(family,str) or family not in MODELS:return _blocked('blocked_unsupported_scope','Unsupported original flagship')
    p=req.get('parameters')
    if not isinstance(p,dict) or not isinstance(req.get('source'),str) or not req['source'].strip():return _blocked('blocked_invalid_inputs','Explicit parameter object and caller source required')
    model=MODELS[family];unknown=set(p)-model.REQUIRED
    if unknown:return _blocked('blocked_invalid_inputs','Unknown parameters: '+', '.join(sorted(unknown)))
    missing=model.REQUIRED-set(p)
    if missing:return {'status':'needs_clarification','questions':[{'field':'parameters.'+k,'question':'Provide explicit '+k} for k in sorted(missing)],'engineering_accepted':False}
    try:
        model._validate(p)
        digest=requirement_sha256(req)
    except (TypeError,ValueError,OverflowError) as e:return _blocked('blocked_invalid_inputs',str(e))
    return {'status':'compiled_stage0','requirement':copy.deepcopy(req),'requirement_sha256':digest,
            'workflow_call':{'action':'run','requirement':copy.deepcopy(req)},'provenance':'caller_supplied_pending_confirmation',
            'engineering_accepted':False,'scope':'original_stage0_only'}

def run(args):
    if not isinstance(args,dict) or set(args)!={'action','requirement'} or args['action'] not in ('compile','run'):return _blocked('blocked_invalid_inputs','Only compile/run actions with one authored requirement are accepted')
    compiled=compile_requirement(args['requirement'])
    if args['action']=='compile' or compiled['status']!='compiled_stage0':return compiled
    req=compiled['requirement'];model=MODELS[req['family']]
    try:
        result=model.run(req['parameters']);candidates=result.get('candidates',[])
        verified=model.verify(req['parameters'],candidates[0]) if candidates else {'ok':True,'kind':'no_candidate_result'}
    except (ValueError,TypeError,OverflowError) as e:return _blocked('blocked_invalid_inputs',str(e))
    if not verified['ok']:return _blocked('blocked_verification','Selected Stage0 candidate did not reproduce')
    outcome='infeasible_stage0' if not candidates else 'candidate_pending_human_confirmation'
    if candidates and candidates[0].get('thermal_ok') is False:outcome='candidate_requires_changes'
    return {'status':'completed_stage0','outcome':outcome,'scope':'original_stage0_only','requirement':req,
            'requirement_sha256':compiled['requirement_sha256'],'result':result,'verification':verified,
            'verified_selected_candidates':1 if candidates else 0,'engineering_accepted':False,'persisted':False}

TOOL={'name':'flagship_workflow','description':'Readonly original H2/W2W/P2 Stage0 structured requirements: compile, finite search and selected-candidate recheck. No family strength release.',
      'annotations':{'readOnlyHint':True},'inputSchema':{'type':'object','additionalProperties':False,'required':['action','requirement'],
      'properties':{'action':{'type':'string','enum':['compile','run']},'requirement':requirement_schema()}}}
