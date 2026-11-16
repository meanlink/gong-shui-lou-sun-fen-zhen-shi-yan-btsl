from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Job, JobEvent
from src.schemas.job import JobInput, PriorityInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import jobs, scheduler
from src.services.audit import record
from src.utils.serialization import job_dict, event_dict
router=APIRouter(prefix='/jobs')
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    return [job_dict(j) for j in db.scalars(select(Job).order_by(Job.id.desc()).limit(100))]
@router.post('',status_code=201)
def create(data:JobInput,db=Depends(get_db),u=Depends(can_write)):
    j=jobs.create(db,data,u); scheduler.event(db,j.id,'job.created',{'by':u.email,'kind':j.kind})
    record(db,u.email,'job.create',{'id':j.id,'params':j.params,'kind':j.kind})
    db.commit(); jobs.enqueue(j.id); return job_dict(j)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    return job_dict(j)
@router.post('/{id}/approve')
def approve(id:int,db=Depends(get_db),u=Depends(admin_only)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    if j.status!='completed':raise HTTPException(409,'仅已完成结果可以批准')
    j.approved=True; record(db,u.email,'job.approve',{'id':id}); db.commit()
    return job_dict(j)
@router.post('/{id}/cancel')
def cancel(id:int,db=Depends(get_db),u=Depends(can_write)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    scheduler.cancel(db,j,u.email); record(db,u.email,'job.cancel',{'id':id}); db.commit()
    return job_dict(j)
@router.post('/{id}/retry')
def retry(id:int,db=Depends(get_db),u=Depends(can_write)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    scheduler.retry(db,j,u.email); record(db,u.email,'job.retry',{'id':id})
    db.commit(); jobs.enqueue(j.id); return job_dict(j)
@router.post('/{id}/priority')
def priority(id:int,data:PriorityInput,db=Depends(get_db),u=Depends(can_write)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    if j.status not in ('queued','running'): raise HTTPException(409,'试验已结束，无法改变类别')
    if j.kind!=data.kind:
        j.kind=data.kind; scheduler.event(db,j.id,'job.priority',{'by':u.email,'kind':data.kind})
        record(db,u.email,'job.priority',{'id':id,'kind':data.kind}); db.commit()
    return job_dict(j)
@router.get('/{id}/events')
def events(id:int,db=Depends(get_db),u=Depends(current_user)):
    if not db.get(Job,id): raise HTTPException(404,'分析任务不存在')
    return [event_dict(e) for e in db.scalars(select(JobEvent).where(JobEvent.job_id==id).order_by(JobEvent.id.desc()).limit(50))]
