"use strict";
const $=id=>document.getElementById(id), token=document.querySelector('meta[name="aion-token"]').content;
let active=null, cc=null, mc=null, attachments=[], busy=false, timer, version=0, listVersion=0;
async function api(path,body){const r=await fetch(path,{method:body?"POST":"GET",headers:{"X-Aion-Token":token,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});const v=await r.json();if(!r.ok)throw Error(v.error||"Falha");return v;}
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function status(text){$("status").textContent=text;}
function error(e){status("Erro · "+e.message);}
function enable(){for(const id of ["message","send","image","file","archive","compact","new","action"])$(id).disabled=busy||(!active&&!["new","action"].includes(id));}
function closeDrawer(){$("sidebar").classList.remove("open");$("drawer-toggle").setAttribute("aria-expanded","false");}
async function list(more=false){
 const v=++listVersion,q=new URLSearchParams({query:$("search").value,archived:$("archived").checked});if(more&&cc)q.set("cursor",cc);
 const page=await api("/api/conversations?"+q);if(v!==listVersion)return;if(!more)$("conversations").replaceChildren();
 for(const c of page.items){const b=node("button",undefined,"conversation"+(active?.id===c.id?" active":""));b.append(node("strong",c.title),node("small",new Date(c.updated_at).toLocaleString("pt-BR")+" · "+c.message_count+" mensagens"));b.onclick=()=>open(c).catch(error);$("conversations").append(b);}
 cc=page.next_cursor;$("more-conversations").hidden=!cc;
}
function renderMessage(m,states){
 const card=node("article",undefined,"message "+m.role);card.dataset.messageId=m.id;
 const h=node("header");h.append(node("span",{user:"Você",assistant:"AION",system:"Sistema",task:"Tarefa"}[m.role]||m.role));
 const t=node("time",new Date(m.created_at).toLocaleString("pt-BR"));t.dateTime=m.created_at;h.append(t);card.append(h,node("p",m.content));
 if(m.attachments.length)card.append(node("small","Anexos em quarentena: "+m.attachments.length));
 if(m.task_metadata){const state=states[m.task_metadata.id]||m.task_metadata.state;card.append(node("div",m.task_metadata.classification+" · "+state,"task-state"));
 if(["PENDING","RUNNING","WAITING_APPROVAL"].includes(state)){const b=node("button","Cancelar tarefa");b.onclick=()=>api("/api/cancel",{cid:m.conversation_id,message_id:m.id}).then(async()=>{await messages();await list();}).catch(error);card.append(b);}}
 if(["assistant","task"].includes(m.role))for(const [value,label]of[["useful","Útil"],["needs_revision","Revisar"]]){const b=node("button",label);b.onclick=()=>api("/api/feedback",{cid:m.conversation_id,message_id:m.id,value}).then(async()=>{await list();status("Feedback salvo");}).catch(error);card.append(b);}
 return card;
}
async function messages(more=false){
 if(!active)return;const v=version,q=new URLSearchParams({cid:active.id});if(more&&mc)q.set("cursor",mc);
 const page=await api("/api/messages?"+q);if(v!==version)return;const states={};for(const m of page.items)if(m.task_metadata&&!states[m.task_metadata.id])states[m.task_metadata.id]=m.task_metadata.state;
 const cards=page.items.reverse().map(m=>renderMessage(m,states));if(more)$("history").prepend(...cards);else $("history").replaceChildren(...cards);
 mc=page.next_cursor;$("more-messages").hidden=!mc;if(!more)$("history").scrollTop=$("history").scrollHeight;
}
async function open(c){if(busy)return;version++;active=c;attachments=[];$("attachment-list").replaceChildren();$("title").textContent=c.title;$("message").value="";enable();closeDrawer();await messages();await list();status("Indisponível · modelo não conectado");}
$("new").onclick=()=>api("/api/create",{title:"Conversa · "+new Date().toLocaleDateString("pt-BR")}).then(open).catch(error);
$("search").oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>list().catch(error),250);};
$("archived").onchange=()=>list().catch(error);$("more-conversations").onclick=()=>list(true).catch(error);$("more-messages").onclick=()=>messages(true).catch(error);
$("drawer-toggle").onclick=()=>{const b=$("sidebar").classList.toggle("open");$("drawer-toggle").setAttribute("aria-expanded",String(b));};
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeDrawer();});
$("archive").onclick=async()=>{try{await api("/api/archive",{cid:active.id});await list();status("Conversa arquivada · histórico preservado");}catch(e){error(e);}};
$("compact").onclick=async()=>{try{await api("/api/compact",{cid:active.id});status("Checkpoint local salvo · histórico preservado");}catch(e){error(e);}};
for(const id of ["image","file"])$(id).onchange=async e=>{
 const f=e.target.files[0];if(!f||!active)return;busy=true;enable();status("Enviando anexo…");
 try{const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(",")[1]);r.onerror=reject;r.readAsDataURL(f);});
 const a=await api("/api/attach",{cid:active.id,name:f.name,mime:f.type,data});attachments.push(a.id);
 const chip=node("span",a.name+" · "+a.size+" bytes "),b=node("button","Remover");b.type="button";b.onclick=()=>{attachments=attachments.filter(x=>x!==a.id);chip.remove();};chip.append(b);$("attachment-list").append(chip);status("Anexo salvo em quarentena");
 }catch(e){error(e);}finally{busy=false;enable();e.target.value="";}};
$("composer").onsubmit=async e=>{e.preventDefault();if(!active||busy)return;busy=true;enable();status("Enviando…");
 try{await api("/api/send",{cid:active.id,content:$("message").value,attachments,action:$("action").value||null});$("message").value="";attachments=[];$("attachment-list").replaceChildren();await messages();await list();status("Concluído · salvo localmente · modelo/executor não conectados");}
 catch(e){error(e);}finally{busy=false;enable();}};
list().catch(error);
