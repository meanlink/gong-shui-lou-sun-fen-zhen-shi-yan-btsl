"""全站试验调度：名额上限、抢修优先、防饿死、原子领取与成绩发布守卫。

- 负责人设定同时计算上限；调低上限只等在途结束，不强杀。
- 抢修试验优先；连续启动三次抢修后，最早入队的普通试验先行；同类按入队顺序。
- 调度员通过配置行写锁串行化，领取用条件更新兜底，并发领取不超上限。
- 每次领取颁发执行令牌（attempt + executor），只有当前有效执行者能发布成绩；
  取消、接管或已完成都会使旧令牌失效，迟到成绩拒收，名额不会重复释放。
"""
import time, uuid
from fastapi import HTTPException
from sqlalchemy import select, update, func
from src.models import Job, SchedulerConfig, JobEvent

EMERGENCY_STREAK_LIMIT = 3   # 连续抢修启动达到此次数后，最早普通试验先行
MAX_CONCURRENT_CAP = 8       # 同时计算上限的可设范围 1~8


def event(db, job_id, name, detail=None):
    db.add(JobEvent(job_id=job_id, event=name, detail=detail or {}, at=time.time()))


def get_config(db):
    cfg = db.get(SchedulerConfig, 1)
    if not cfg:
        cfg = SchedulerConfig(id=1, max_concurrent=2, emergency_streak=0, updated_by='system', updated_at=time.time())
        db.add(cfg)
        db.flush()
    return cfg


def set_limit(db, limit, actor):
    if not isinstance(limit, int) or not 1 <= limit <= MAX_CONCURRENT_CAP:
        raise HTTPException(422, f'同时计算上限须为 1~{MAX_CONCURRENT_CAP} 的整数')
    cfg = get_config(db)
    cfg.max_concurrent = limit
    cfg.updated_by = actor
    cfg.updated_at = time.time()
    db.flush()
    return cfg


def _lock_config(db):
    # 配置行写锁：串行化所有调度员（PostgreSQL 行锁 / SQLite 库级写锁），
    # 使“统计在途 + 领取”成为临界区，保证并发领取不超上限。
    db.execute(update(SchedulerConfig).where(SchedulerConfig.id == 1).values(emergency_streak=SchedulerConfig.emergency_streak))


def _running_count(db):
    return db.scalar(select(func.count()).select_from(Job).where(Job.status == 'running')) or 0


def _earliest(db, kind):
    return db.scalars(select(Job).where(Job.status == 'queued', Job.kind == kind).order_by(Job.created_at, Job.id).limit(1)).first()


def _pick(db, cfg):
    """抢修优先；连续三次抢修后最早普通试验先行；同类按入队顺序。"""
    urgent = _earliest(db, 'emergency')
    normal = _earliest(db, 'normal')
    if not urgent:
        return normal
    if not normal:
        return urgent
    return urgent if cfg.emergency_streak < EMERGENCY_STREAK_LIMIT else normal


def dispatch(db, worker_id):
    """填满空闲名额，返回 [(job_id, attempt, token)]；调用方提交事务后再启动执行。"""
    cfg = get_config(db)
    _lock_config(db)
    claimed, running, guard = [], _running_count(db), 0
    while running < cfg.max_concurrent and guard < 64:
        guard += 1
        job = _pick(db, cfg)
        if not job:
            break
        attempt, token = job.attempt + 1, f'{worker_id}-{uuid.uuid4().hex[:10]}'
        takeover = job.attempt > 0
        # 原子领取：只有仍处于 queued 的试验才能被本调度员领走
        res = db.execute(update(Job).where(Job.id == job.id, Job.status == 'queued').values(
            status='running', attempt=attempt, executor=token, claimed_at=time.time(), queue_note=''))
        if res.rowcount != 1:
            db.expire(job)  # 被并发取消或领走，重新选择
            continue
        cfg.emergency_streak = cfg.emergency_streak + 1 if job.kind == 'emergency' else 0
        event(db, job.id, 'job.takeover' if takeover else 'job.dispatch', {'attempt': attempt, 'executor': token})
        claimed.append((job.id, attempt, token))
        running += 1
    _refresh_queue_notes(db, cfg)
    db.flush()
    return claimed


def finalize(db, job_id, attempt, token, *, result=None, error=None):
    """发布成绩：只有持有当前有效令牌的执行者能写入；取消/接管/重试使旧令牌失效。

    条件更新保证名额只随这一次状态跃迁释放，重复发布或迟到发布都被拒收。
    """
    now = time.time()
    if error is None:
        values = dict(status='completed', result=result if result is not None else {}, error='', finished_at=now, queue_note='')
    else:
        values = dict(status='failed', error=str(error)[:990], finished_at=now, queue_note='')
    res = db.execute(update(Job).where(
        Job.id == job_id, Job.status == 'running', Job.attempt == attempt, Job.executor == token).values(**values))
    if res.rowcount != 1:
        j = db.get(Job, job_id)
        event(db, job_id, 'job.result_rejected', {'attempt': attempt, 'executor': token, 'status': j.status if j else 'missing'})
        db.flush()
        return False
    event(db, job_id, 'job.completed' if error is None else 'job.failed',
          {'attempt': attempt, 'executor': token, **({'error': str(error)[:300]} if error is not None else {})})
    db.flush()
    return True


def cancel(db, job, actor):
    """取消等待或运行中的试验。与完成互斥：取消先提交则拒收成绩，完成先提交则保留成绩。"""
    was = job.status
    res = db.execute(update(Job).where(Job.id == job.id, Job.status.in_(['queued', 'running'])).values(
        status='cancelled', finished_at=time.time(), queue_note=''))
    if res.rowcount != 1:
        raise HTTPException(409, '试验已结束，成绩保留，无法取消')
    job.status, job.finished_at, job.queue_note = 'cancelled', time.time(), ''
    event(db, job.id, 'job.cancelled', {'by': actor, 'was': was})
    db.flush()
    return job


def retry(db, job, actor):
    """原地重试失败或已取消的试验：不新建试验、不重复释放名额。"""
    res = db.execute(update(Job).where(Job.id == job.id, Job.status.in_(['failed', 'cancelled'])).values(
        status='queued', error='', executor='', finished_at=None, claimed_at=None, queue_note='等待重新调度'))
    if res.rowcount != 1:
        raise HTTPException(409, '仅失败或已取消的试验可以重试')
    job.status, job.error, job.executor, job.finished_at, job.claimed_at, job.queue_note = 'queued', '', '', None, None, '等待重新调度'
    event(db, job.id, 'job.retry', {'by': actor})
    db.flush()
    return job


def recover_interrupted(db):
    """worker 启动时恢复中断的试验：原试验回到排队等待接管，旧执行令牌随之失效。"""
    for j in db.scalars(select(Job).where(Job.status == 'running')):
        event(db, j.id, 'job.recovered', {'attempt': j.attempt, 'executor': j.executor})
        j.status, j.executor, j.claimed_at, j.queue_note = 'queued', '', None, '执行中断，已恢复原试验等待重新调度'
    db.flush()


def _simulate_order(queued, streak):
    """按调度策略推演排队顺序，用于解释每个试验还要等多久。"""
    normals = [j for j in queued if j.kind == 'normal']
    urgents = [j for j in queued if j.kind == 'emergency']
    order, s = [], streak
    while normals or urgents:
        if urgents and (not normals or s < EMERGENCY_STREAK_LIMIT):
            order.append(urgents.pop(0)); s += 1
        else:
            order.append(normals.pop(0)); s = 0
    return order


def explain_queue(db, cfg=None):
    """每个排队试验的预计顺位与原因（追查排队原因）。"""
    cfg = cfg or get_config(db)
    running = _running_count(db)
    queued = list(db.scalars(select(Job).where(Job.status == 'queued').order_by(Job.created_at, Job.id)))
    order = _simulate_order(queued, cfg.emergency_streak)
    out = []
    for pos, j in enumerate(order, 1):
        if running >= cfg.max_concurrent:
            reason = f'计算名额已满（{running}/{cfg.max_concurrent}），等待在途试验结束'
        else:
            reason = '出现空闲名额，等待调度器领取'
        if pos > 1:
            reason += f'；前方还有 {pos - 1} 个试验'
        if j.kind == 'normal' and any(x.kind == 'emergency' for x in order[:pos - 1]):
            reason += '；抢修试验优先'
        out.append((j, pos, reason))
    return out


def _refresh_queue_notes(db, cfg):
    for j, pos, reason in explain_queue(db, cfg):
        if j.queue_note != reason:
            j.queue_note = reason


def status_snapshot(db):
    cfg = get_config(db)
    running = list(db.scalars(select(Job).where(Job.status == 'running').order_by(Job.claimed_at, Job.id)))
    queued = explain_queue(db, cfg)
    events = list(db.scalars(select(JobEvent).order_by(JobEvent.id.desc()).limit(30)))
    return cfg, running, queued, events
