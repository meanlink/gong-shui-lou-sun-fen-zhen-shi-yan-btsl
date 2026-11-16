export const Role={admin:'业务负责人',analyst:'分析员',viewer:'观察员'};
export const JobStatus={queued:'排队中',running:'计算中',completed:'已完成',failed:'执行失败',cancelled:'已取消'};
export const JobKind={normal:'普通试验',emergency:'抢修试验'};
export const JobEventName={'job.created':'创建入队','job.dispatch':'调度领取','job.takeover':'中断后接管','job.recovered':'中断恢复原试验','job.completed':'计算完成','job.failed':'计算失败','job.cancelled':'取消试验','job.retry':'原地重试','job.priority':'调整类别','job.result_rejected':'拒收迟到成绩'};
