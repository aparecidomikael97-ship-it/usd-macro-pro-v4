export default function(component) {
 const {data,parentElement,setTriggerValue}=component;
 let root=parentElement.querySelector('.aq-chat-root');
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 if(!root){
  root=el('section',undefined,'aq-chat-root ref-workspace ref-component-root');root.dataset.workspace='aion';parentElement.append(root);
  root.innerHTML=`<header class="aq-chat-header ref-toolbar"><div class="aq-chat-brand"><span aria-hidden="true">◈</span><div><strong>ATLASQUANT</strong><small>ECOSSISTEMA · AION</small></div></div><span class="aq-chat-mode">Prévia local · sem provider</span><button type="button" data-route="central">← Central</button></header>
  <div class="aq-chat-layout"><aside><h2>Seu AION</h2><p>Um núcleo. Uma conversa.<br>Todos os ambientes.</p><nav class="ref-sidebar" aria-label="Funções do AION"></nav><footer>Histórico desta sessão.<br>Persistência durável não conectada.</footer></aside><main class="aq-chat-main ref-canvas">
  <div class="aq-chat-heading"><div><small>INTELIGÊNCIA ATLASQUANT</small><h1>Converse com o AION</h1><button type="button" class="aq-chat-home" data-route="home" hidden>← Conversa principal</button></div><details class="aq-chat-functions ref-drawer"><summary>Funções do AION</summary><nav aria-label="Funções do AION no mobile"></nav></details></div>
  <div class="aq-chat-session"><span>Conversa da sessão</span><small class="aq-chat-id"></small></div>
  <div class="aq-chat-pagination"><button type="button" class="aq-chat-older">← Mensagens anteriores</button><span class="aq-chat-count"></span><button type="button" class="aq-chat-newer">Mensagens recentes →</button></div>
  <section class="aq-chat-history" aria-label="Histórico da conversa" tabindex="0"></section>
  <button type="button" class="aq-chat-bottom" hidden>Ir para mensagens recentes ↓</button>
  <form class="aq-chat-composer"><label for="aq-chat-message">Sua mensagem</label><textarea id="aq-chat-message" rows="3" maxlength="8000" placeholder="Pergunte, explore uma ideia ou peça um plano…" aria-describedby="aq-chat-help"></textarea><div class="aq-chat-chips"></div><div class="aq-chat-actions"><label class="aq-chat-attach">＋ Anexar arquivo ou imagem<input class="aq-chat-files" type="file" multiple aria-label="Anexar arquivo ou imagem"></label><span class="aq-chat-keyhint">Enter envia · Shift+Enter quebra linha</span><button type="button" class="aq-chat-stop" hidden>Parar envio visual</button><button type="submit" class="aq-chat-send">Enviar ↑</button></div><p class="aq-chat-turn-notice" role="status" aria-live="polite" hidden></p><small id="aq-chat-help">Anexos: apenas nome, tipo e tamanho. Ingestão segura ainda não ativa.</small></form>
  <p class="aq-chat-live" role="status" aria-live="polite" aria-atomic="true">Pronto para conversar · planejamento local, sem execução.</p>
  </main></div>`; // Constant markup only. All dynamic content uses textContent.
  root._state={files:[],busy:false,pending:'',lastAck:'',renderKey:'',timer:null,stopped:false};
 }
 const state=root._state,q=s=>root.querySelector(s),history=q('.aq-chat-history'),input=q('#aq-chat-message');
 root.dataset.artReady='true';q('main').classList.toggle('ref-detail',data.selected==='chat');q('.aq-chat-home').hidden=data.selected!=='chat';
 q('[data-route="central"]').hidden=!data.central;
 q('.aq-chat-id').textContent=data.conversation_id;
 const live=text=>q('.aq-chat-live').textContent=text;
 // This is the state of the most recent *turn*, never an execution gate for new messages.
 const renderTurnNotice=()=>{
  const note=q('.aq-chat-turn-notice');
  const last=data.page===0 && !data.notice && Array.isArray(data.entries)
   ? [...data.entries].reverse().find(entry=>entry.role==='assistant') : null;
  const turn=last && data.turns ? data.turns[last.turn_id] : null;
  const waiting=turn?.state==='WAITING_APPROVAL' && turn.approval?.required===true && turn.approval?.granted!==true;
  const blocked=turn?.state==='BLOCKED';
  note.hidden=!(waiting||blocked);
  note.dataset.state=waiting?'WAITING_APPROVAL':blocked?'BLOCKED':'';
  note.textContent=waiting
   ? 'O pedido anterior aguarda aprovação humana pelo fluxo autorizado. Nenhuma ação foi executada; você pode continuar conversando.'
   : blocked
    ? 'O pedido anterior foi bloqueado pela política, não a conversa. Nenhuma ação foi executada; você pode enviar outra mensagem.'
    : '';
 };
 renderTurnNotice();
 const enabled=()=>{input.disabled=state.busy;q('.aq-chat-send').disabled=state.busy;q('.aq-chat-files').disabled=state.busy;q('.aq-chat-stop').hidden=!state.busy;q('form').setAttribute('aria-busy',String(state.busy));};
 const finish=()=>{state.busy=false;clearTimeout(state.timer);enabled();input.focus({preventScroll:true});};
 const chipList=()=>{q('.aq-chat-chips').replaceChildren();state.files.forEach((f,index)=>{const chip=el('span',`${f.filename} · ${f.size_bytes} bytes`,'aq-chat-chip'),b=el('button','×');b.type='button';b.setAttribute('aria-label',`Remover ${f.filename}`);b.disabled=state.busy;b.onclick=()=>{state.files.splice(index,1);chipList();};chip.append(b);q('.aq-chat-chips').append(chip);});};
 for(const nav of root.querySelectorAll('nav')){nav.replaceChildren();for(const item of data.navigation){if(data.selected==='chat'&&item.route==='home'&&nav.closest('.aq-chat-functions'))continue;const button=el('button',item.label);button.type='button';button.dataset.route=item.route;nav.append(button);}}
 root.querySelectorAll('[data-route]').forEach(button=>button.onclick=()=>{if(!state.busy)setTriggerValue('navigate',button.dataset.route);});
 const key=JSON.stringify([data.page,data.total,data.ack]);
 if(state.renderKey!==key){
  const nearBottom=history.scrollHeight-history.scrollTop-history.clientHeight<80;
  const position=history.scrollTop;history.replaceChildren();
  if(!data.entries.length){const empty=el('div',undefined,'aq-chat-empty');empty.append(el('div','◉','aq-chat-orb'),el('h2','O que vamos explorar hoje?'),el('p','Converse, anexe uma referência ou peça um plano. Você verá o que foi entendido e o que ainda precisa de aprovação.'));
   const suggestions=el('div',undefined,'aq-chat-suggestions');for(const text of ['Como está o sistema?','Resumo de tarefas','Explique o contexto']){const b=el('button',text);b.type='button';b.onclick=()=>{input.value=text;input.focus();};suggestions.append(b);}empty.append(suggestions);history.append(empty);}
  for(const entry of data.entries){
   const card=el('article',undefined,'aq-chat-message '+entry.role);card.dataset.turnId=entry.turn_id;
   const assistantLabel=data.product_mode?'AION · leitura local verificada':'AION · plano local';
   card.append(el('strong',entry.role==='user'?'Você':assistantLabel),el('p',entry.display_text??entry.content));
   for(const f of entry.attachments||[])card.append(el('small',`Anexo metadata · ${f.name} · ${f.mime_type} · ${f.size_bytes} bytes`));
   if(entry.role==='assistant'){
    const turn=data.turns[entry.turn_id]||{},status=turn.state||'BLOCKED';card.dataset.state=status;
    const statusLabel=({PLANNED:'Planejado',WAITING_APPROVAL:'Aguardando aprovação',BLOCKED:'Bloqueado',REJECTED:'Não aceito',CONFIRMED_SUCCESS:'Confirmado'})[status]||status;
    card.append(el('span',statusLabel+' · '+status,'aq-chat-state '+status.toLowerCase()),el('small','Capability · '+turn.capability));
    for(const blocker of turn.blockers||[])card.append(el('small',blocker,'aq-chat-blocker'));
    if(turn.approval?.required){const note=el('div','Aprovação necessária · não concedida. Use o fluxo autorizado quando estiver integrado.','aq-chat-approval');card.append(note);}
    // A positive approval claim requires an independently verified future contract.
    const grantEvidence=turn.approval?.granted===false?'False':'NOT_VERIFIED';
    const proof=el('details',undefined,'aq-chat-proof'),summary=el('summary','Proof Mode · contrato e evidência');proof.append(summary);
    proof.ontoggle=()=>{if(!proof.open||proof.dataset.loaded)return;proof.dataset.loaded='true';proof.append(el('p',`Capability: ${turn.capability} · Policy: ${turn.policy_state} · Approval: ${turn.approval?.state||'NOT_APPLICABLE'} · granted=${grantEvidence}`),el('p',turn.evidence),el('p',turn.receipt),el('p','Provider não conectado · modo local. Estado online do runtime não observado.'));
     const stages=el('ol');for(const stage of turn.stages||[])stages.append(el('li',`${stage.stage} · ${stage.state}`));proof.append(stages,el('small',`Turno: ${entry.turn_id}`));};card.append(proof);
   }history.append(card);
  }
  if(state.pending||nearBottom||state.renderKey==='')history.scrollTop=history.scrollHeight;else history.scrollTop=position;
  if(data.page>0)history.scrollTop=0;
  state.renderKey=key;
 }
 q('.aq-chat-older').hidden=!data.has_older;q('.aq-chat-newer').hidden=!data.has_newer;q('.aq-chat-count').textContent=`${data.total} mensagens nesta sessão · janela de até 40`;
 q('.aq-chat-older').onclick=()=>setTriggerValue('page','older');q('.aq-chat-newer').onclick=()=>setTriggerValue('page','newer');
 history.onscroll=()=>q('.aq-chat-bottom').hidden=history.scrollHeight-history.scrollTop-history.clientHeight<80;
 q('.aq-chat-bottom').onclick=()=>{history.scrollTop=history.scrollHeight;q('.aq-chat-bottom').hidden=true;};
 if(data.ack&&data.ack===state.pending&&data.ack!==state.lastAck){state.lastAck=data.ack;state.pending='';if(!data.notice){input.value='';state.files=[];chipList();}finish();live(data.notice|| (state.stopped?'Envio visual interrompido · plano registrado, nenhuma ação executada.':'Turno avaliado · nenhuma ação executada.'));}
 if(data.notice)live(data.notice);
 q('.aq-chat-files').onchange=e=>{const files=Array.from(e.target.files||[]);if(state.files.length+files.length>16){live('Até 16 anexos por turno. Nenhum arquivo enviado.');e.target.value='';return;}for(const file of files)state.files.push({filename:file.name,mime_type:file.type||'application/octet-stream',size_bytes:file.size});chipList();live('Metadata selecionada · conteúdo não enviado nem ingerido.');e.target.value='';};
 q('form').onsubmit=e=>{e.preventDefault();if(state.busy)return;if(!input.value.trim()){live('Escreva uma mensagem para enviar.');input.focus();return;}state.pending=crypto.randomUUID();state.busy=true;state.stopped=false;enabled();chipList();live('Enviando para avaliação local…');setTriggerValue('send',{request_id:state.pending,conversation_id:data.conversation_id,message:input.value,attachments:state.files});
  state.timer=setTimeout(()=>{finish();live('Avaliação sem retorno. Seu texto foi preservado; não há execução ou sucesso confirmado.');},15000);};
 input.onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();q('form').requestSubmit();}};
 q('.aq-chat-stop').onclick=()=>{state.stopped=true;q('.aq-chat-stop').disabled=true;live('Envio visual interrompido. O preflight local pode terminar; nenhuma execução foi iniciada.');};
 if(!state.busy)q('.aq-chat-stop').disabled=false;enabled();
 const resize=()=>{const rect=root.getBoundingClientRect(),viewport=window.visualViewport;root.style.setProperty('--aq-chat-height',Math.max(280,(viewport?.height||window.innerHeight)-Math.max(0,rect.top)-12)+'px');};
 resize();window.visualViewport?.addEventListener('resize',resize);window.addEventListener('resize',resize);
 return ()=>{window.visualViewport?.removeEventListener('resize',resize);window.removeEventListener('resize',resize);};
}
