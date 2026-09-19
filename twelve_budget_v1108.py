"""Persistent reservations for the sole Twelve Data collector.

Every attempted single-symbol time_series request costs one reserved credit,
including errors/timeouts. Reservations precede HTTP and use GitHub SHA CAS.
No other application may call the provider; UI modules read the shared cache.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import base64
import json
import re
import math
import requests

BUDGET_PATH = 'dados/twelve_budget_v1108.json'
DAILY_LIMIT = 480
HOURLY_LIMIT = 28
MINUTE_LIMIT = 6
WINDOW_SECONDS = 62


def utc(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('UTC timestamp required')
    return value.astimezone(timezone.utc)


def next_day(now):
    return (utc(now).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))


def classify_limit(message):
    text = str(message).lower()
    # Explicit minute wording must win over generic "API credits" wording.
    if any(x in text for x in ('current minute','per minute','next minute','minute limit','rpm')):
        return 'LIMITE_MINUTO'
    if any(x in text for x in ('for the day','daily limit','daily credits','next day')):
        return 'COTA_DIARIA'
    return 'COTA_OU_PLANO'


class BudgetUnavailable(RuntimeError):
    pass


class GitHubStore:
    def __init__(self, token, repo, branch, path=BUDGET_PATH):
        self.token, self.repo, self.branch, self.path = token, repo, branch, path

    def load(self):
        if not self.token or not self.repo:
            raise BudgetUnavailable('Persistência do orçamento não configurada')
        r=requests.get(f'https://api.github.com/repos/{self.repo}/contents/{self.path}',
                       headers={'Authorization':f'Bearer {self.token}'}, params={'ref':self.branch}, timeout=20)
        if r.status_code==404: return {}, None
        if r.status_code!=200: raise BudgetUnavailable(f'Leitura do orçamento: HTTP {r.status_code}')
        data=r.json()
        try:
            state=json.loads(base64.b64decode(data['content']).decode('utf-8'))
            if not isinstance(state,dict) or not state: raise ValueError('nonempty object required')
            return state,data['sha']
        except Exception:
            raise BudgetUnavailable('Arquivo de orçamento inválido') from None

    def save(self, state, revision):
        body={'message':'V11.0.8: reserva de créditos Twelve Data', 'branch':self.branch,
              'content':base64.b64encode(json.dumps(state,ensure_ascii=False).encode()).decode()}
        if revision: body['sha']=revision
        r=requests.put(f'https://api.github.com/repos/{self.repo}/contents/{self.path}',
                       headers={'Authorization':f'Bearer {self.token}'},json=body,timeout=25)
        if r.status_code in (409,422): return False
        if r.status_code not in (200,201): raise BudgetUnavailable(f'Reserva do orçamento: HTTP {r.status_code}')
        return True


class Budget:
    def __init__(self, store):
        self.store=store

    def _current(self, state, now):
        now=utc(now); state=deepcopy(state)
        if state:
            try:
                day=datetime.strptime(state['day'],'%Y-%m-%d').date()
                if day>now.date() or int(state['used'])<0: raise ValueError()
                if any(not math.isfinite(float(t)) for t in state.get('recent',[])): raise ValueError()
                if any(int(v)<0 for v in state.get('hours',{}).values()): raise ValueError()
            except Exception:
                raise BudgetUnavailable('Contagem diária inválida; coleta bloqueada') from None
        if not state or state['day']!=now.date().isoformat():
            state={'version':1,'day':now.date().isoformat(),'used':0,'hours':{},'recent':[]}
        if state.get('blocked_until'):
            try:
                if utc(state['blocked_until'])<=now:
                    for key in ('blocked_until','block_type','block_reason'): state.pop(key,None)
            except Exception:
                raise BudgetUnavailable('Prazo de bloqueio inválido') from None
        return state

    def _change(self, fn, now=None):
        now=utc(now)
        for _ in range(4):
            try: raw,revision=self.store.load()
            except Exception as exc: raise BudgetUnavailable('Falha ao ler orçamento') from exc
            state=self._current(raw,now)
            result,changed=fn(state,now)
            if not changed: return result
            try: saved=self.store.save(state,revision)
            except Exception as exc: raise BudgetUnavailable('Falha ao salvar orçamento') from exc
            if saved: return result
        raise BudgetUnavailable('Conflito ao reservar créditos; consulta adiada')

    def summary(self, now=None):
        now=utc(now); state=self._current(self.store.load()[0],now)
        return {**state,'limit':DAILY_LIMIT,'remaining':max(0,DAILY_LIMIT-int(state['used'])),
                'reset_at':next_day(now).isoformat(), 'pace_ceiling':min(DAILY_LIMIT,28+now.hour*20)}

    def bootstrap(self, old_status, scanner, now=None):
        """Carry today's old count/block forward instead of resetting at install."""
        def seed(s,n):
            before=deepcopy(s)
            old=(scanner.get('autopilot_v107',{}) or {}).get('daily_budget',{}) or {}
            if old.get('day')==s['day']:
                s['used']=max(int(s['used']),int(old.get('calls',0)))
            reason=str(old_status.get('twelve_daily_block_reason',''))
            try: same_day=utc(old_status.get('last_run')).date()==n.date()
            except Exception: same_day=False
            if same_day and old_status.get('twelve_daily_blocked') and classify_limit(reason)=='COTA_DIARIA':
                self._set_block(s,reason,n)
            s['migration_done']=True
            return s,s!=before
        return self._change(seed,now)

    def reserve(self, now=None):
        def take(s,n):
            if s.get('blocked_until'):
                return (False,s.get('block_type'),s.get('blocked_until')),False
            if int(s['used'])>=DAILY_LIMIT:
                return (False,'ORCAMENTO_DIARIO',next_day(n).isoformat()),False
            hour=n.strftime('%H'); hours=s.get('hours',{})
            if int(hours.get(hour,0))>=HOURLY_LIMIT or int(s['used'])>=min(DAILY_LIMIT,28+n.hour*20):
                until=n.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
                return (False,'RITMO_DIARIO',until.isoformat()),False
            epoch=n.timestamp()
            recent=[float(t) for t in s.get('recent',[]) if epoch-float(t)<WINDOW_SECONDS]
            if any(t>epoch for t in recent): raise BudgetUnavailable('Relógio anterior à última reserva')
            if len(recent)>=MINUTE_LIMIT:
                until=datetime.fromtimestamp(min(recent)+WINDOW_SECONDS,timezone.utc)
                return (False,'LIMITE_MINUTO',until.isoformat()),False
            s['used']=int(s['used'])+1
            s.setdefault('hours',{})[hour]=int(hours.get(hour,0))+1
            s['recent']=[*recent,epoch]
            s['last_reserved_at']=n.isoformat()
            return (True,'',''),True
        return self._change(take,now)

    def _set_block(self,s,message,n):
        kind=classify_limit(message)
        until=next_day(n) if kind=='COTA_DIARIA' else n+timedelta(seconds=62 if kind=='LIMITE_MINUTO' else 3600)
        s.update(block_type=kind,blocked_until=until.isoformat(),block_reason=str(message)[:700])
        if kind=='COTA_DIARIA':
            match=re.search(r'(\d+)\s+API credits were used',str(message),re.I)
            if match: s['used']=max(int(s['used']),int(match.group(1)))

    def block(self,message,now=None):
        def stop(s,n):
            self._set_block(s,message,n)
            return s,True
        return self._change(stop,now)
