#!/usr/bin/env python3
import base64, hashlib, re, hmac, json, mimetypes, os, secrets, sqlite3, threading, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = os.getenv('IMPACTO_DB', str(ROOT / 'data' / 'impacto.sqlite3'))
VOUCHER_KEY = os.getenv('VOUCHER_HMAC_KEY', 'local-development-only-change-me').encode()
ENV = os.getenv('IMPACTO_ENV', 'development').lower()
MAX_BODY_BYTES = int(os.getenv('MAX_BODY_BYTES', '1048576'))
LOGIN_WINDOW_SECONDS = int(os.getenv('LOGIN_WINDOW_SECONDS', '300'))
LOGIN_MAX_ATTEMPTS = int(os.getenv('LOGIN_MAX_ATTEMPTS', '10'))
WEB = ROOT / 'web'
LOGIN_ATTEMPTS = {}

LOCK = threading.RLock()
WEIGHTS = {'cause_alignment':20,'territory':15,'budget_ticket':15,'mechanism_program':15,'capacity_readiness':10,'evidence_indicators':10,'funder_preference':5,'schedule_urgency':5,'residual_operational_risk':5}

def now(): return datetime.now(timezone.utc).isoformat()
def canonical(x): return json.dumps(x, sort_keys=True, separators=(',',':'), ensure_ascii=False)
def valid_sha256(x):
    return bool(re.fullmatch(r'[0-9a-fA-F]{64}', str(x or '')))

def clean_text(x, max_len=500):
    x = str(x if x is not None else '').strip()
    return x[:max_len]

def valid_positive_int(x, allow_zero=True):
    try:
        n = int(x)
        return n >= 0 if allow_zero else n > 0
    except Exception:
        return False

def client_ip(handler):
    return (handler.client_address[0] if handler.client_address else 'unknown')

def rate_limited_login(handler):
    key = client_ip(handler)
    t = datetime.now(timezone.utc).timestamp()
    bucket = LOGIN_ATTEMPTS.setdefault(key, [])
    LOGIN_ATTEMPTS[key] = [x for x in bucket if t - x < LOGIN_WINDOW_SECONDS]
    if len(LOGIN_ATTEMPTS[key]) >= LOGIN_MAX_ATTEMPTS:
        return True
    LOGIN_ATTEMPTS[key].append(t)
    return False

def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10); c.row_factory = sqlite3.Row; c.execute('PRAGMA foreign_keys=ON')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, compliance_status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, org_id TEXT NOT NULL REFERENCES organizations(id), created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS programs(id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), name TEXT NOT NULL, cause TEXT NOT NULL, territory TEXT NOT NULL, budget_cents INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'draft', criteria_version TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS opportunities(id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), program_id TEXT NOT NULL REFERENCES programs(id), title TEXT NOT NULL, description TEXT NOT NULL, requested_cents INTEGER NOT NULL, territory TEXT NOT NULL, cause TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'submitted', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), object_type TEXT NOT NULL, object_id TEXT NOT NULL, filename TEXT NOT NULL, sha256 TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'received', created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS match_runs(id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), opportunity_id TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS vouchers(code_hash TEXT PRIMARY KEY, plan TEXT NOT NULL, redeemed INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS entitlements(org_id TEXT, feature TEXT, source TEXT, expires_at TEXT, PRIMARY KEY(org_id,feature,source));
    CREATE TABLE IF NOT EXISTS plan_catalog(plan_key TEXT PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER, features TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS subscriptions(id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), plan_key TEXT NOT NULL, status TEXT NOT NULL, provider TEXT NOT NULL, current_period_end TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit_event(id INTEGER PRIMARY KEY AUTOINCREMENT, org_id TEXT, actor_id TEXT, action TEXT NOT NULL, object_type TEXT, object_id TEXT, payload TEXT NOT NULL, prev_hash TEXT, event_hash TEXT NOT NULL, at TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS ix_program_org ON programs(org_id, created_at); CREATE INDEX IF NOT EXISTS ix_opp_org ON opportunities(org_id, created_at);
    ''')
    c.executemany('INSERT OR IGNORE INTO plan_catalog VALUES(?,?,?,?,?)', [('funder_basic','Funder Básico',0,canonical(['programs:1','seats:3','reports:basic']),1),('funder_premium','Funder Premium',None,canonical(['programs:5','seats:15','reports:advanced','workflow:custom']),1),('enterprise','Enterprise',None,canonical(['programs:unlimited','sso:requested','api:requested','audit:export']),1)])
    c.commit(); return c

def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16); dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210000)
    return base64.urlsafe_b64encode(salt + dk).decode()
def password_ok(password, stored):
    try:
        raw=base64.urlsafe_b64decode(stored.encode()); return hmac.compare_digest(password_hash(password,raw[:16]),stored)
    except Exception: return False
def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()
def code_hash(code): return hmac.new(VOUCHER_KEY, code.strip().upper().encode(), hashlib.sha256).hexdigest()
def audit(c, org_id, actor_id, action, typ, oid, payload):
    prev=c.execute('SELECT event_hash FROM audit_event ORDER BY id DESC LIMIT 1').fetchone(); ph=prev['event_hash'] if prev else ''
    eh=hashlib.sha256((ph+canonical({'org_id':org_id,'actor_id':actor_id,'action':action,'object_type':typ,'object_id':oid,'payload':payload})).encode()).hexdigest()
    c.execute('INSERT INTO audit_event(org_id,actor_id,action,object_type,object_id,payload,prev_hash,event_hash,at) VALUES(?,?,?,?,?,?,?,?,?)',(org_id,actor_id,action,typ,oid,canonical(payload),ph,eh,now())); return eh

def match_score(o, program=None):
    blockers=[]; program=program or {}
    if program.get('status') not in (None,'open'): blockers.append({'code':'CALL_NOT_OPEN','message':'A chamada não está aberta'})
    if program.get('territory') and o.get('territory') != program.get('territory'): blockers.append({'code':'TERRITORY_MISMATCH','message':'Território incompatível'})
    if program.get('budget_cents') is not None and int(o.get('requested_cents',0)) > int(program['budget_cents']): blockers.append({'code':'BUDGET_EXCEEDED','message':'Valor acima do orçamento da chamada'})
    if blockers: return {'eligibility':'blocked','compatibility':None,'confidence':0,'blockers':blockers,'why_match':[],'why_not':['Há bloqueio determinístico'],'risks':['Revisão humana obrigatória'],'missing_information':[],'next_action':'Corrigir os bloqueios','engine_version':'match-engine@0.2.0'}
    vals=o.get('signals') or {}; total=sum(WEIGHTS[k]*max(0,min(1,float(vals.get(k,0)))) for k in WEIGHTS); present=sum(k in vals for k in WEIGHTS)
    missing=[k for k in WEIGHTS if k not in vals]; confidence=round(100*present/len(WEIGHTS))
    pos=sorted(((WEIGHTS[k]*float(vals.get(k,0)),k) for k in WEIGHTS if k in vals),reverse=True)[:3]
    neg=sorted(((WEIGHTS[k]*float(vals.get(k,0)),k) for k in WEIGHTS if k in vals))[:3]
    return {'eligibility':'eligible' if present==len(WEIGHTS) else 'needs_review','compatibility':round(total,2) if present else 'insufficient_data','confidence':confidence,'blockers':[],'why_match':[k for _,k in pos],'why_not':[k for _,k in neg if float(vals.get(k,0))<.5],'risks':['Score indicativo; decisão final humana'],'missing_information':missing,'next_action':'Completar dados faltantes e registrar revisão humana' if missing else 'Registrar decisão humana','engine_version':'match-engine@0.2.0'}

def seed():
    c=db(); org=c.execute('SELECT id FROM organizations LIMIT 1').fetchone()
    if org: return
    oid='org-demo'; c.execute('INSERT INTO organizations VALUES(?,?,?,?,?)',(oid,'Instituto Impacto Demo','funder','pending',now()))
    c.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',('user-admin','admin@impacto.local',password_hash('Admin@123'),'admin',oid,now()))
    c.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',('user-analyst','analista@impacto.local',password_hash('Analista@123'),'analyst',oid,now()))
    pid='program-demo'; c.execute('INSERT INTO programs VALUES(?,?,?,?,?,?,?,?,?)',(pid,oid,'Programa Comunidades 2026','educação','Brasil',50000000,'open','demo/c1',now()))
    c.execute('INSERT OR IGNORE INTO vouchers VALUES(?,?,?)',(code_hash('DEV-DEMO-2026'),'osc_premium',0)); c.commit()

def auth(c, handler):
    token=handler.headers.get('Authorization','').removeprefix('Bearer ').strip()
    if not token: return None
    row=c.execute('SELECT u.*,o.name org_name,o.kind org_kind FROM sessions s JOIN users u ON u.id=s.user_id JOIN organizations o ON o.id=u.org_id WHERE s.token_hash=? AND s.expires_at>?',(token_hash(token),now())).fetchone()
    return dict(row) if row else None
def body(handler):
    try:
        n = int(handler.headers.get('Content-Length','0'))
        if n < 0 or n > MAX_BODY_BYTES:
            raise ValueError('Corpo da requisição excede o limite')
        return json.loads(handler.rfile.read(n) or b'{}')
    except ValueError:
        raise
    except Exception:
        raise ValueError('JSON inválido')
def send(handler,status,obj,typ='application/json'):
    raw=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False).encode()
    handler.send_response(status)
    handler.send_header('Content-Type',typ+'; charset=utf-8')
    handler.send_header('Content-Length',str(len(raw)))
    handler.send_header('X-Content-Type-Options','nosniff')
    handler.send_header('X-Frame-Options','DENY')
    handler.send_header('Referrer-Policy','strict-origin-when-cross-origin')
    handler.send_header('Cache-Control','no-store' if typ == 'application/json' else 'no-cache')
    handler.end_headers(); handler.wfile.write(raw)
def require(handler,c,roles=None):
    u=auth(c,handler)
    if not u: send(handler,401,{'title':'Autenticação necessária','status':401}); return None
    if roles and u['role'] not in roles: send(handler,403,{'title':'Permissão insuficiente','status':403}); return None
    return u
def rowdict(row): return dict(row) if row else None

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        p=urlparse(self.path).path
        if p in ('/','/index.html'): return self.static('index.html','text/html')
        if p=='/manifest.webmanifest': return self.static('manifest.webmanifest','application/manifest+json')
        if p=='/sw.js': return self.static('sw.js','application/javascript')
        if p.startswith('/static/'): return self.static(p.split('/')[-1],mimetypes.guess_type(p)[0] or 'text/plain')
        c=db()
        if p=='/healthz': return send(self,200,{'status':'ok','product_state':'local-mvp','database':'sqlite'})
        u=require(self,c)
        if not u: return
        if p=='/v1/plans': return send(self,200,{'items':[dict(r) | {'features':json.loads(r['features'])} for r in c.execute('SELECT * FROM plan_catalog WHERE active=1 ORDER BY price_cents IS NULL, price_cents') ]})
        if p=='/v1/me': return send(self,200,{k:u[k] for k in ('id','email','role','org_id','org_name','org_kind')})
        if p=='/v1/entitlements':
            sub=c.execute("SELECT * FROM subscriptions WHERE org_id=? AND status IN ('sandbox_active','active') ORDER BY created_at DESC LIMIT 1",(u['org_id'],)).fetchone(); grants=[dict(r) for r in c.execute('SELECT feature,source,expires_at FROM entitlements WHERE org_id=?',(u['org_id'],))]; return send(self,200,{'plan':dict(sub) if sub else None,'grants':grants,'billing_mode':'sandbox'})
        if p=='/v1/dashboard/summary':
            def count(table): return c.execute(f'SELECT COUNT(*) n FROM {table} WHERE org_id=?',(u['org_id'],)).fetchone()['n']
            return send(self,200,{'programs':count('programs'),'opportunities':count('opportunities'),'documents':count('documents'),'matches':count('match_runs'),'audit_events':count('audit_event')})
        if p=='/v1/programs': return send(self,200,{'items':[dict(r) for r in c.execute('SELECT * FROM programs WHERE org_id=? ORDER BY created_at DESC',(u['org_id'],))]})
        if p=='/v1/opportunities': return send(self,200,{'items':[dict(r) for r in c.execute('SELECT o.*,p.name program_name FROM opportunities o JOIN programs p ON p.id=o.program_id WHERE o.org_id=? ORDER BY o.created_at DESC',(u['org_id'],))]})
        if p=='/v1/documents': return send(self,200,{'items':[dict(r) for r in c.execute('SELECT * FROM documents WHERE org_id=? ORDER BY created_at DESC',(u['org_id'],))]})
        if p=='/v1/audit-events': return send(self,200,{'items':[dict(r) for r in c.execute('SELECT id,action,object_type,object_id,event_hash,prev_hash,at FROM audit_event WHERE org_id=? ORDER BY id DESC',(u['org_id'],))]})
        if p=='/v1/admin/overview':
            if u['role']!='admin': return send(self,403,{'title':'Admin only','status':403})
            return send(self,200,{'organizations':c.execute('SELECT COUNT(*) n FROM organizations').fetchone()['n'],'users':c.execute('SELECT COUNT(*) n FROM users').fetchone()['n'],'programs':c.execute('SELECT COUNT(*) n FROM programs').fetchone()['n'],'opportunities':c.execute('SELECT COUNT(*) n FROM opportunities').fetchone()['n'],'documents':c.execute('SELECT COUNT(*) n FROM documents').fetchone()['n']})
        if p=='/v1/fiscal/mechanisms': return send(self,200,{'status':'pending_review','items':[],'message':'Nenhuma regra fiscal foi verificada; validação profissional necessária.'})
        return send(self,404,{'title':'Não encontrado','status':404})
    def static(self,name,typ):
        path=WEB/name
        if not path.exists(): return send(self,404,b'Not found','text/plain')
        return send(self,200,path.read_bytes(),typ)
    def do_POST(self):
        p=urlparse(self.path).path
        try: b=body(self)
        except ValueError as e: return send(self,400,{'title':str(e),'status':400})
        c=db()
        if p=='/v1/auth/register':
            email=str(b.get('email','')).strip().lower(); password=str(b.get('password','')); name=str(b.get('organization_name','')).strip() or 'Organização sem nome'; kind=b.get('kind','osc')
            if '@' not in email or len(password)<10: return send(self,422,{'title':'E-mail ou senha inválidos','status':422})
            if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(): return send(self,409,{'title':'E-mail já cadastrado','status':409})
            oid=str(uuid.uuid4()); uid=str(uuid.uuid4()); c.execute('INSERT INTO organizations VALUES(?,?,?,?,?)',(oid,name,kind,'pending',now())); c.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(uid,email,password_hash(password),'owner',oid,now())); audit(c,oid,uid,'user.registered','user',uid,{'email':email}); c.commit(); return send(self,201,{'user_id':uid,'org_id':oid})
        if p=='/v1/auth/login':
            if rate_limited_login(self):
                return send(self,429,{'title':'Muitas tentativas. Tente novamente mais tarde.','status':429})
            u=c.execute('SELECT * FROM users WHERE email=?',(str(b.get('email','')).strip().lower(),)).fetchone()
            if not u or not password_ok(str(b.get('password','')),u['password_hash']): return send(self,401,{'title':'Credenciais inválidas','status':401})
            token=secrets.token_urlsafe(32); c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token_hash(token),u['id'],datetime.fromtimestamp(datetime.now().timestamp()+86400,timezone.utc).isoformat(),now())); c.commit(); return send(self,200,{'token':token,'user':{'id':u['id'],'email':u['email'],'role':u['role'],'org_id':u['org_id']}})
        if p=='/v1/auth/logout':
            raw=self.headers.get('Authorization','').removeprefix('Bearer ').strip()
            if raw: c.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(raw),)); c.commit()
            return send(self,204,b'', 'text/plain')
        u=require(self,c)
        if not u: return
        if p=='/v1/subscriptions':
            plan=str(b.get('plan_key','')); planrow=c.execute('SELECT * FROM plan_catalog WHERE plan_key=? AND active=1',(plan,)).fetchone()
            if not planrow: return send(self,422,{'title':'Plano inválido','status':422})
            sid=str(uuid.uuid4()); c.execute('INSERT INTO subscriptions VALUES(?,?,?,?,?,?,?)',(sid,u['org_id'],plan,'sandbox_active','sandbox',None,now())); audit(c,u['org_id'],u['id'],'subscription.created','subscription',sid,{'plan_key':plan,'provider':'sandbox'}); c.commit(); return send(self,201,{'id':sid,'status':'sandbox_active','plan_key':plan,'requires_external_gateway':True})
        if p=='/v1/programs':
            if u['role'] not in ('admin','owner','analyst'): return send(self,403,{'title':'Sem permissão','status':403})
            name=clean_text(b.get('name'),160); cause=clean_text(b.get('cause','não definida'),120); territory=clean_text(b.get('territory','não definido'),160)
            if not name or not valid_positive_int(b.get('budget_cents',0)): return send(self,422,{'title':'Nome e orçamento válidos são obrigatórios','status':422})
            status=clean_text(b.get('status','draft'),30); criteria=clean_text(b.get('criteria_version','c1'),60)
            if status not in ('draft','open','closed','paused'): return send(self,422,{'title':'Status de programa inválido','status':422})
            pid=str(uuid.uuid4()); c.execute('INSERT INTO programs VALUES(?,?,?,?,?,?,?,?,?)',(pid,u['org_id'],name,cause,territory,int(b.get('budget_cents',0)),status,criteria,now())); audit(c,u['org_id'],u['id'],'program.created','program',pid,{'name':name,'cause':cause,'territory':territory,'budget_cents':int(b.get('budget_cents',0)),'status':status,'criteria_version':criteria}); c.commit(); return send(self,201,{'id':pid})
        if p=='/v1/opportunities':
            oid=str(uuid.uuid4()); program=c.execute('SELECT * FROM programs WHERE id=? AND org_id=?',(b.get('program_id'),u['org_id'])).fetchone()
            if not program: return send(self,404,{'title':'Programa não encontrado','status':404})
            title=clean_text(b.get('title'),200); desc=clean_text(b.get('description'),4000); territory=clean_text(b.get('territory'),160); cause=clean_text(b.get('cause'),120)
            if not title or not desc or not territory or not cause or not valid_positive_int(b.get('requested_cents',0)): return send(self,422,{'title':'Campos obrigatórios inválidos','status':422})
            status=clean_text(b.get('status','submitted'),30)
            if status not in ('draft','submitted','approved','funded','closed'): return send(self,422,{'title':'Status de oportunidade inválido','status':422})
            x=(oid,u['org_id'],program['id'],title,desc,int(b.get('requested_cents',0)),territory,cause,status,now()); c.execute('INSERT INTO opportunities VALUES(?,?,?,?,?,?,?,?,?,?)',x); audit(c,u['org_id'],u['id'],'opportunity.created','opportunity',oid,{'program_id':program['id'],'title':title,'requested_cents':int(b.get('requested_cents',0)),'territory':territory,'cause':cause,'status':status}); c.commit(); return send(self,201,{'id':oid})
        if p=='/v1/documents':
            filename=clean_text(b.get('filename'),255); digest=str(b.get('sha256','')).lower()
            if not filename or not valid_sha256(digest): return send(self,422,{'title':'filename e SHA-256 válido são obrigatórios','status':422})
            object_type=clean_text(b.get('object_type','unknown'),60); object_id=clean_text(b.get('object_id',''),80)
            if object_type not in ('organization','program','opportunity','user'): return send(self,422,{'title':'Tipo de objeto inválido','status':422})
            did=str(uuid.uuid4()); c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)',(did,u['org_id'],object_type,object_id,filename,digest,'received',now())); audit(c,u['org_id'],u['id'],'document.received','document',did,{'filename':filename,'sha256':digest}); c.commit(); return send(self,201,{'id':did,'status':'received'})
        if p=='/v1/matches/evaluate':
            program=c.execute('SELECT * FROM programs WHERE id=? AND org_id=?',(b.get('program_id'),u['org_id'])).fetchone()
            if not program: return send(self,404,{'title':'Programa não encontrado','status':404})
            opportunity_id=b.get('opportunity_id')
            if opportunity_id:
                op=c.execute('SELECT * FROM opportunities WHERE id=? AND org_id=? AND program_id=?',(opportunity_id,u['org_id'],program['id'])).fetchone()
                if not op: return send(self,404,{'title':'Oportunidade não encontrada para este programa','status':404})
                o=dict(op); o.update({'signals':b.get('signals') or {}})
            else:
                o=dict(b)
            result=match_score(o,rowdict(program)); rid=str(uuid.uuid4()); c.execute('INSERT INTO match_runs VALUES(?,?,?,?,?)',(rid,u['org_id'],o.get('id',opportunity_id or ''),canonical(result),now())); audit(c,u['org_id'],u['id'],'match.evaluated','match_run',rid,result); c.commit(); result.update({'id':rid,'criteria_version':program['criteria_version'],'computed_at':now()}); return send(self,200,result)
        if p=='/v1/vouchers/redeem':
            with LOCK:
                row=c.execute('SELECT * FROM vouchers WHERE code_hash=?',(code_hash(b.get('code','')),)).fetchone()
                if not row or row['redeemed']: return send(self,404,{'title':'Voucher indisponível','status':404})
                c.execute('UPDATE vouchers SET redeemed=1 WHERE code_hash=?',(row['code_hash'],)); c.execute('INSERT OR IGNORE INTO entitlements VALUES(?,?,?,?)',(u['org_id'],'premium','voucher',None)); audit(c,u['org_id'],u['id'],'voucher.redeemed','voucher',row['code_hash'],{'source':'voucher'}); c.commit(); return send(self,200,{'redeemed':True,'feature':'premium'})
        return send(self,404,{'title':'Não encontrado','status':404})

def main():
    if ENV == 'production' and VOUCHER_KEY == b'local-development-only-change-me':
        raise SystemExit('VOUCHER_HMAC_KEY obrigatório em produção')
    if os.getenv('IMPACTO_SEED_DEMO','0') == '1':
        seed()
    port=int(os.getenv('PORT','8080')); print(f'impacto {ENV} listening on :{port}',flush=True); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
if __name__=='__main__': main()
