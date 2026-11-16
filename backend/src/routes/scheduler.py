from fastapi import APIRouter, Depends
from src.config.database import get_db
from src.middlewares.auth import current_user, admin_only
from src.services import scheduler
from src.services.audit import record
from src.schemas.scheduler import LimitInput
from src.utils.serialization import job_dict, event_dict, config_dict
router=APIRouter(prefix='/scheduler')
@router.get('')
def snapshot(db=Depends(get_db),u=Depends(current_user)):
    cfg,running,queued,events=scheduler.status_snapshot(db)
    return {'config':config_dict(cfg),'running':[job_dict(j) for j in running],
            'queued':[{**job_dict(j),'position':pos,'reason':reason} for j,pos,reason in queued],
            'events':[event_dict(e) for e in events]}
@router.put('/config')
def set_config(data:LimitInput,db=Depends(get_db),u=Depends(admin_only)):
    cfg=scheduler.set_limit(db,data.max_concurrent,u.email)
    record(db,u.email,'scheduler.limit',{'max_concurrent':cfg.max_concurrent})
    db.commit()
    return config_dict(cfg)
