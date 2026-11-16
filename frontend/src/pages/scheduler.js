import {jobs,scheduler} from '../api/entities.js';
import {session} from '../stores/session.js';
import {heading} from '../components/common/shell.js';
import {status} from '../components/common/status.js';
import {JobKind,JobEventName} from '../constants/enums.js';
import {esc,date,notify} from '../utils/dom.js';
import {submit} from '../hooks/forms.js';
const canWrite=()=>session.user.role!=='viewer';
const badge=k=>'<span class="kind-badge '+esc(k)+'">'+esc(JobKind[k]||k)+'</span>';
const detail=d=>Object.entries(d||{}).map(([k,v])=>k==='attempt'?'第'+v+'次执行':k==='executor'?'执行者 '+v:k==='by'?'操作 '+v:k==='kind'?esc(JobKind[v]||v):esc(k)+' '+esc(v)).join(' · ');
export async function schedulePage(){
 const [snap,all]=await Promise.all([scheduler.get(),jobs.list()]);
 const cfg=snap.config,running=snap.running,queued=snap.queued,events=snap.events,isAdmin=session.user.role==='admin';
 const ended=all.filter(j=>['completed','failed','cancelled'].includes(j.status)).slice(0,8);
 const item=(j,extra,actions)=>'<article class="sched-item"><div><strong>#'+j.id+' '+esc(j.name)+'</strong> '+badge(j.kind)+'<p>'+extra+'</p></div><div class="actions">'+actions+'</div></article>';
 return heading('04 / SCHEDULING','全站试验调度','夜巡批量试参与抢修研判共用计算名额。负责人设定同时计算上限；抢修优先，连续启动三次抢修后最早普通试验先行，同类按入队顺序。','<button class="button" id="refresh-sched">刷新调度 ↻</button>')
 +'<section class="sched-hero"><div class="meter"><span>计算名额占用</span><strong>'+running.length+'<small> / '+cfg.max_concurrent+'</small></strong><p>调低上限后在途试验继续运行直至结束，系统不强杀，名额随结束自动收敛。连续抢修启动 '+cfg.emergency_streak+'/'+cfg.streak_limit+'，达到后最早普通试验先行。</p><small>上限由 '+esc(cfg.updated_by||'系统')+(cfg.updated_at?' 于 '+date(cfg.updated_at):'')+' 设定 · 范围 1~'+cfg.limit_cap+'</small></div>'
 +'<form id="limit-form" class="limit-form"><label>同时计算上限<input type="number" name="max_concurrent" min="1" max="'+cfg.limit_cap+'" step="1" value="'+cfg.max_concurrent+'" required '+(isAdmin?'':'disabled')+'></label><button type="submit" class="primary" '+(isAdmin?'':'disabled')+'>保存上限</button><p class="hint">仅负责人可调整；立即生效于后续领取。</p></form></section>'
 +'<div class="sched-grid"><section class="panel"><div class="section-title"><h2>计算占用</h2><span>'+running.length+' 个在途</span></div>'
 +(running.length?running.map(j=>item(j,'执行者 '+esc(j.executor||'—')+' · 第 '+j.attempt+' 次执行 · 开始于 '+date(j.claimed_at),status('running')+'<button class="text-button" data-cancel="'+j.id+'" '+(canWrite()?'':'disabled')+'>取消</button>')).join(''):'<div class="empty">当前没有在途计算。</div>')+'</section>'
 +'<section class="panel"><div class="section-title"><h2>排队等待</h2><span>'+queued.length+' 个待调度</span></div>'
 +(queued.length?queued.map(j=>item(j,'第 '+j.position+' 顺位 · '+esc(j.reason)+'<br><small>入队于 '+date(j.created_at)+'</small>','<button class="text-button" data-priority="'+j.id+'" data-kind="'+(j.kind==='emergency'?'normal':'emergency')+'" '+(canWrite()?'':'disabled')+'>'+(j.kind==='emergency'?'改回普通':'标为抢修')+'</button><button class="text-button" data-cancel="'+j.id+'" '+(canWrite()?'':'disabled')+'>取消</button>')).join(''):'<div class="empty">没有排队中的试验。</div>')+'</section></div>'
 +'<div class="sched-grid"><section class="panel"><div class="section-title"><h2>最近结束</h2><span>失败或已取消可原地重试</span></div>'
 +(ended.length?ended.map(j=>item(j,status(j.status)+' · 结束于 '+date(j.finished_at||j.created_at)+(j.error?' · '+esc(j.error.slice(0,80)):''),(j.status==='failed'||j.status==='cancelled'?'<button class="text-button" data-retry="'+j.id+'" '+(canWrite()?'':'disabled')+'>重试</button>':'')+'<a class="text-button" href="#/results/'+j.id+'">查看 ↗</a>')).join(''):'<div class="empty">尚无结束的试验。</div>')+'</section>'
 +'<section class="panel"><div class="section-title"><h2>调度与接管记录</h2><span>最近 '+events.length+' 条</span></div><ul class="timeline">'
 +(events.length?events.map(e=>'<li><strong>'+esc(JobEventName[e.event]||e.event)+' · 试验 #'+e.job_id+'</strong><span>'+detail(e.detail)+' · '+date(e.at)+'</span></li>').join(''):'<li><strong>暂无调度记录</strong><span>提交试验后此处显示领取、接管与取消轨迹</span></li>')+'</ul></section></div>';
}
export function bindScheduler(refresh){
 document.querySelector('#refresh-sched').onclick=refresh;
 submit(document.querySelector('#limit-form'),async f=>{await scheduler.setLimit(Number(f.get('max_concurrent')));notify('上限已保存：在途试验继续运行，名额随结束收敛');await refresh();});
 document.querySelectorAll('[data-cancel]').forEach(b=>b.onclick=async()=>{try{await jobs.cancel(b.dataset.cancel);notify('已取消；若执行者迟到交卷，成绩将被拒收');await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-priority]').forEach(b=>b.onclick=async()=>{try{await jobs.priority(b.dataset.priority,b.dataset.kind);await refresh();}catch(e){notify(e.message,true);}});
 document.querySelectorAll('[data-retry]').forEach(b=>b.onclick=async()=>{try{await jobs.retry(b.dataset.retry);notify('已重新排队：原试验原地重试，不新建任务');await refresh();}catch(e){notify(e.message,true);}});
}
