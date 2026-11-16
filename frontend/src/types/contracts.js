/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,kind:string,result:Object,approved:boolean,attempt:number,executor:string,queue_note:string}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean}} ReportSchedule */
/** @typedef {{max_concurrent:number,emergency_streak:number,streak_limit:number,limit_cap:number}} SchedulerConfig */
/** @typedef {{id:number,job_id:number,event:string,detail:Object,at:number}} JobEvent */
export {};
