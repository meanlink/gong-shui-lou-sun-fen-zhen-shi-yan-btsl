import os, time, json, logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Dataset, Report
from src.services.business import analyze
from src.services.reports import deliver
from src.services import scheduler
from src.services.audit import record
logging.basicConfig(level=logging.INFO)
WORKER_ID = f'w{os.getpid()}'
POOL = ThreadPoolExecutor(max_workers=scheduler.MAX_CONCURRENT_CAP)
def run_job(job_id, attempt, token):
    """执行一次有效领取；只有持有当前令牌的执行者能发布成绩。"""
    result, error = None, None
    try:
        with Session() as db:
            j = db.get(Job, job_id)
            d = db.get(Dataset, j.dataset_id) if j else None
            if not j or not d: raise ValueError('试验或数据批次不存在')
            records, params = d.records, j.params
        result = analyze(records, params)
        json.dumps(result, allow_nan=False)
    except Exception as e:
        logging.exception('Analysis failed')
        result, error = None, str(e)[:990]
    try:
        with Session() as db:
            if scheduler.finalize(db, job_id, attempt, token, result=result, error=error):
                record(db, 'worker', 'job.completed' if error is None else 'job.failed', {'id': job_id})
            else:
                record(db, 'worker', 'job.result_rejected', {'id': job_id, 'attempt': attempt})
            db.commit()
    except Exception:
        logging.exception('Finalize failed')
def cycle():
    """按上限填满空闲名额；Redis 消息只是唤醒，SQL 排队状态是持久兜底。"""
    try:
        with Session() as db:
            claimed = scheduler.dispatch(db, WORKER_ID)
            db.commit()
        for job_id, attempt, token in claimed:
            POOL.submit(run_job, job_id, attempt, token)
    except Exception:
        logging.exception('Dispatch failed')
def tick():
    with Session() as db:
        for r in db.scalars(select(Report).where(Report.enabled==True, Report.next_run<=time.time())):
            d = deliver(db, r)
            if d: record(db, 'worker', 'report.delivered', {'id': r.id, 'delivery': d.id})
        db.commit()
def main():
    r = Redis.from_url(REDIS_URL, socket_timeout=3)
    # This Compose stack has a single worker. A crash must not strand its jobs.
    for _ in range(30):
        try:
            with Session() as db:
                scheduler.recover_interrupted(db)
                db.commit()
            break
        except Exception:
            logging.exception('Recovery retry'); time.sleep(2)
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            r.blpop('analysis:queue', timeout=1)
        except Exception:
            logging.exception('Redis wait failed; SQL fallback tick'); time.sleep(2)
        try:
            cycle()
            tick()
        except Exception:
            logging.exception('Worker retry'); time.sleep(2)
if __name__=='__main__':main()
