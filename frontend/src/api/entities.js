import {api} from './client.js';
export const datasets={list:()=>api('/datasets'),get:id=>api('/datasets/'+id),create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)})};
export const jobs={list:()=>api('/jobs'),get:id=>api('/jobs/'+id),create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),approve:id=>api('/jobs/'+id+'/approve',{method:'POST'}),cancel:id=>api('/jobs/'+id+'/cancel',{method:'POST'}),retry:id=>api('/jobs/'+id+'/retry',{method:'POST'}),priority:(id,kind)=>api('/jobs/'+id+'/priority',{method:'POST',body:JSON.stringify({kind})}),events:id=>api('/jobs/'+id+'/events')};
export const scheduler={get:()=>api('/scheduler'),setLimit:max_concurrent=>api('/scheduler/config',{method:'PUT',body:JSON.stringify({max_concurrent})})};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
