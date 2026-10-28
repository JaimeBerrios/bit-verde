const $ = (s) => document.querySelector(s);
const node = (tag, text, className) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;};
async function api(path, body) {
  const response=await fetch('/api'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(15000)});
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Revisa los campos e inténtalo de nuevo.');
  return data;
}
function message(selector,text,error=false){const el=$(selector);el.textContent=text;el.className=error?'error':'success';}
if(document.body.dataset.page==='game'){
 let session, answers=[], index=0;
 const content=$('#game-content');
 async function start(){const button=$('#start');button.disabled=true;message('#game-message','Preparando circuito…');try{session=await api('/trivia/start',{});answers=[];index=0;message('#game-message','');render();}catch(e){message('#game-message',e.message,true);button.disabled=false;}}
 function render(){content.replaceChildren();$('#step').textContent=`PASO ${index+1} DE 3`;content.append(node('h3',session.questions[index].prompt));const options=node('div',undefined,'options');session.questions[index].options.forEach((text,i)=>{const button=node('button',text,'option');button.onclick=()=>{answers.push(i);index++;if(index<3)render();else finish();};options.append(button);});content.append(options);}
 async function finish(){content.replaceChildren(node('p','Comprobando reparación…'));try{const result=await api(`/trivia/${session.session_id}/submit`,{answers});$('#step').textContent=`${result.score} / 3 ACIERTOS`;content.replaceChildren(node('h3',result.passed?'¡Circuito reparado!':'Cada intento te enseña algo.'));if(result.passed){content.append(node('p','Guarda este token y preséntalo al staff para canjear tu Bus de Datos Saludable.'),node('code',result.token,'token'));}result.feedback.forEach(text=>content.append(node('p',text)));const restart=node('button','Jugar otra vez →','button');restart.onclick=start;restart.id='start';content.append(restart);}catch(e){message('#game-message',e.message+' Si perdiste la conexión, no envíes otra ronda automáticamente.',true);const retry=node('button','Reintentar envío','button');retry.onclick=finish;content.append(retry);}}
 $('#start').onclick=start;
}
if(document.body.dataset.page==='registration'){
 $('#donation-form').onsubmit=async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;message('#form-message','Registrando entrega…');const body=Object.fromEntries(new FormData(event.target));body.quantity=Number(body.quantity);try{const data=await api('/donations',body);event.target.hidden=true;message('#form-message','¡Entrega registrada! Guarda tu comprobante.');const receipt=$('#receipt');receipt.hidden=false;receipt.replaceChildren(node('h3','Comprobante de entrega'),node('code',data.ticket,'token'));for(const text of [`Participante: ${data.alias}`,`Categoría: ${data.category}`,`${data.quantity} piezas · ${data.weight_kg} kg estimados`,`Fecha: ${new Date(data.created_at).toLocaleString('es-SV')}`])receipt.append(node('p',text));const details=node('details');details.append(node('summary','Ver payload UTF-8 en bytes (representación educativa)'),node('pre','HEX: '+data.payload_hex+'\n\nBIN: '+data.payload_binary));const print=node('button','Guardar / imprimir comprobante','button');print.onclick=()=>window.print();const another=node('a','Registrar otra entrega →','text-link');another.href='/registro';receipt.append(details,print,another);}catch(e){message('#form-message',e.message+' Si hubo una interrupción de red, confirma con el staff antes de repetir la entrega.',true);}finally{button.disabled=false;}};
}
if(document.body.dataset.page==='dashboard'){
 async function refresh(){try{const data=await api('/metrics');$('#items').textContent=data.items;$('#registrations').textContent=data.registrations;$('#weight-total').textContent=data.weight_kg.toLocaleString('es-SV',{maximumFractionDigits:3});$('#repaired').textContent=data.repaired;$('#data-flow').replaceChildren(...data.recent.map(row=>{const el=node('div',undefined,'flow-row');el.append(node('strong',row.hex),node('code',row.binary));return el;}));if(!data.recent.length)$('#data-flow').append(node('p','La primera entrega inicia el flujo.'));message('#connection','● En vivo · actualizado '+new Date().toLocaleTimeString('es-SV'));}catch(e){message('#connection','Sin conexión · se conservan los últimos datos. Reintentando…',true);}finally{setTimeout(refresh,5000);}}
 refresh();$('#fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{message('#connection','El navegador no permite activar pantalla completa.',true);}};
}
if(document.body.dataset.page==='staff'){
 let verifiedToken=null;
 $('#token').oninput=()=>{verifiedToken=null;$('#redeem').hidden=true;$('#token-result').textContent='';};
 $('#token-form').onsubmit=async event=>{event.preventDefault();verifiedToken=null;$('#redeem').hidden=true;try{const data=await api('/staff/token?token='+encodeURIComponent($('#token').value));message('#token-result',data.canjeado?'Este token ya fue canjeado.':'Token válido. Confirma el canje al entregar la recompensa.',data.canjeado);if(!data.canjeado){verifiedToken=data.token;$('#redeem').hidden=false;}}catch(e){message('#token-result',e.message,true);}};
 $('#redeem').onclick=async()=>{if(!verifiedToken)return;$('#redeem').disabled=true;try{await api('/staff/redeem',{token:verifiedToken});message('#token-result','CANJEADO ✓ Entrega el Bus de Datos Saludable.');verifiedToken=null;$('#redeem').hidden=true;}catch(e){message('#token-result',e.message,true);}finally{$('#redeem').disabled=false;}};
}
