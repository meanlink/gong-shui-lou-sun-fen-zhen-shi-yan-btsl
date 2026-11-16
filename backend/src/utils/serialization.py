import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','kind','result','error','approved','created_at','finished_at','attempt','executor','claimed_at','queue_note']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination']}
def event_dict(e):
    return {'id':e.id, 'job_id':e.job_id, 'event':e.event, 'detail':e.detail, 'at':e.at}
def config_dict(c):
    from src.services.scheduler import EMERGENCY_STREAK_LIMIT, MAX_CONCURRENT_CAP
    return {'max_concurrent':c.max_concurrent, 'emergency_streak':c.emergency_streak, 'updated_by':c.updated_by, 'updated_at':c.updated_at, 'streak_limit':EMERGENCY_STREAK_LIMIT, 'limit_cap':MAX_CONCURRENT_CAP}
