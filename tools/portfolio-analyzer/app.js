// Portfolio Returns Analyzer — render layer (deterministic; no Date.now/random).
const D = window.__DATA__;
const GREEN='#1a7f5a', RED='#c0392b', BLUE='#2f6db0', GOLD='#c79a3a', GREY='#9aa3ad';
const f$ = v => (v<0?'-$':'$') + Math.abs(Math.round(v)).toLocaleString();
const fp = v => v==null ? '—' : (v>=0?'+':'') + (v*100).toFixed(1) + '%';
const cls = v => v==null ? '' : (v>=0 ? 'pos' : 'neg');
const dstr = ms => { const d=new Date(ms); return (d.getUTCMonth()+1)+'/'+d.getUTCDate()+'/'+d.getUTCFullYear(); };
const state = { account: D.order[0] };
const charts = {};
const mk = id => (charts[id] = echarts.init(document.getElementById(id), null, {renderer:'svg'}));

function cards(){
  const a = D.accounts[state.account];
  const beat = a.end_value - a.clone_end;
  const last = a.years[a.years.length-1];
  const cashpct = (last && last.cash_pct!=null) ? (last.cash_pct*100).toFixed(0)+'%' : '—';
  const rows = [
    ['Current value', f$(a.end_value), 'big'],
    ['Net invested', f$(a.net_contributed), ''],
    ['Lifetime XIRR', fp(a.lifetime_xirr), 'big'],
    ['Cash on sidelines', cashpct, ''],
    ['vs. benchmark clone', (beat>=0?'+':'')+f$(beat), beat>=0?'pos':'neg'],
    ['Max drawdown', fp(a.risk.max_drawdown), 'neg'],
  ];
  document.getElementById('cards').innerHTML = rows.map(([l,v,c]) =>
    `<div class="card"><div class="lab">${l}</div><div class="val ${c}">${v}</div></div>`).join('');
}

function youVsBench(){
  const dl = D.accounts[state.account].daily;
  const ins = dl.events.filter(e=>e.type==='in').map(e=>[e.t,e.cum,e.amt]);
  const outs = dl.events.filter(e=>e.type==='out').map(e=>[e.t,e.cum,e.amt]);
  charts.vsbench.setOption({
    tooltip:{trigger:'axis',axisPointer:{type:'cross'},valueFormatter:v=>v==null?'':f$(v)},
    legend:{bottom:0,data:['Your portfolio','If same $ → '+D.meta.benchmark,'Working capital','Deposit','Withdrawal']},
    grid:{left:72,right:18,top:18,bottom:48}, xAxis:{type:'time'},
    yAxis:{type:'value',axisLabel:{formatter:v=>'$'+(v/1000)+'k'}},
    series:[
      {name:'Working capital',type:'line',step:'end',symbol:'none',itemStyle:{color:GREY},lineStyle:{width:1.5,color:GREY},areaStyle:{color:'rgba(154,163,173,.12)'},data:dl.working_capital},
      {name:'If same $ → '+D.meta.benchmark,type:'line',symbol:'none',itemStyle:{color:GOLD},lineStyle:{width:2,color:GOLD},data:dl.clone},
      {name:'Your portfolio',type:'line',symbol:'circle',symbolSize:7,itemStyle:{color:GREEN},lineStyle:{width:2.5,color:GREEN},data:dl.actual},
      {name:'Deposit',type:'scatter',symbol:'triangle',symbolSize:p=>Math.min(20,6+Math.sqrt(p[2])/35),itemStyle:{color:GREEN},data:ins,
        tooltip:{trigger:'item',formatter:p=>'Deposit '+f$(p.data[2])+'<br>'+dstr(p.data[0])}},
      {name:'Withdrawal',type:'scatter',symbol:'triangle',symbolRotate:180,symbolSize:p=>Math.min(20,6+Math.sqrt(Math.abs(p[2]))/35),itemStyle:{color:RED},data:outs,
        tooltip:{trigger:'item',formatter:p=>'Withdrawal '+f$(p.data[2])+'<br>'+dstr(p.data[0])}}
    ]
  });
}

function waterfall(){
  const a = D.accounts[state.account];
  let dep=0,wd=0,gain=0; a.years.forEach(y=>{ gain+=y.gain; if(y.net_flow>=0)dep+=y.net_flow; else wd+=y.net_flow; });
  const start=a.years[0].start;
  const steps=[['Start',start],['Deposits',dep],['Withdrawals',wd],['Gains',gain],['End',a.end_value]];
  const base=[],val=[],col=[]; let run=0;
  steps.forEach(([lab,amt],i)=>{
    if(i===0||i===4){ base.push(0); val.push(Math.round(amt)); run=amt; col.push(BLUE); }
    else if(amt>=0){ base.push(Math.round(run)); val.push(Math.round(amt)); run+=amt; col.push(GREEN); }
    else { base.push(Math.round(run+amt)); val.push(Math.round(-amt)); run+=amt; col.push(RED); }
  });
  charts.waterfall.setOption({
    tooltip:{trigger:'axis',formatter:p=>steps[p[0].dataIndex][0]+': '+f$(steps[p[0].dataIndex][1])},
    grid:{left:70,right:18,top:18,bottom:28}, xAxis:{type:'category',data:steps.map(s=>s[0])},
    yAxis:{type:'value',axisLabel:{formatter:v=>'$'+(v/1000)+'k'}},
    series:[
      {type:'bar',stack:'w',itemStyle:{color:'transparent'},data:base,silent:true,tooltip:{show:false}},
      {type:'bar',stack:'w',data:val.map((v,i)=>({value:v,itemStyle:{color:col[i]}})),
        label:{show:true,position:'top',fontSize:10,formatter:p=>f$(steps[p.dataIndex][1])}}
    ]
  });
}

function returns(){
  const a = D.accounts[state.account];
  charts.returns.setOption({
    tooltip:{trigger:'axis',valueFormatter:v=>v==null?'—':v.toFixed(1)+'%'}, legend:{bottom:0},
    grid:{left:48,right:16,top:16,bottom:46}, xAxis:{type:'category',data:a.years.map(y=>y.year)},
    yAxis:{type:'value',axisLabel:{formatter:v=>v+'%'}},
    series:[
      {name:'TWR (picks)',type:'bar',itemStyle:{color:GREEN},data:a.years.map(y=>+(y.twr*100).toFixed(1))},
      {name:'XIRR (your $)',type:'bar',itemStyle:{color:BLUE},data:a.years.map(y=>y.xirr==null?null:+(y.xirr*100).toFixed(1))}
    ]
  });
}

function decomp(){
  // Dollars (not % of growth) — robust when a down year's flows ≈ -gain (no blow-up).
  const a = D.accounts[state.account];
  charts.decomp.setOption({
    tooltip:{trigger:'axis',valueFormatter:f$}, legend:{bottom:0},
    grid:{left:54,right:16,top:16,bottom:46}, xAxis:{type:'category',data:a.years.map(y=>y.year)},
    yAxis:{type:'value',axisLabel:{formatter:v=>'$'+(v/1000)+'k'}},
    series:[
      {name:'New money',type:'bar',stack:'s',itemStyle:{color:BLUE},data:a.years.map(y=>Math.round(y.net_flow))},
      {name:'Appreciation',type:'bar',stack:'s',data:a.years.map(y=>({value:Math.round(y.gain),itemStyle:{color:y.gain>=0?GREEN:RED}}))}
    ]
  });
}

function cash(){
  const a = D.accounts[state.account];
  const has = a.years.some(y=>y.cash!=null);
  document.getElementById('cashwrap').style.display = has ? '' : 'none';
  if(!has) return;
  charts.cash.setOption({
    tooltip:{trigger:'axis'}, legend:{bottom:0},
    grid:{left:58,right:50,top:16,bottom:46}, xAxis:{type:'category',data:a.years.map(y=>y.year)},
    yAxis:[{type:'value',name:'$',axisLabel:{formatter:v=>'$'+(v/1000)+'k'}},{type:'value',name:'%',axisLabel:{formatter:v=>v+'%'}}],
    series:[
      {name:'Invested',type:'bar',stack:'v',itemStyle:{color:GREEN},data:a.years.map(y=>y.invested==null?null:Math.round(y.invested))},
      {name:'Cash on sidelines',type:'bar',stack:'v',itemStyle:{color:GOLD},data:a.years.map(y=>y.cash==null?null:Math.round(y.cash))},
      {name:'Cash %',type:'line',yAxisIndex:1,itemStyle:{color:RED},data:a.years.map(y=>y.cash_pct==null?null:+(y.cash_pct*100).toFixed(1))}
    ]
  });
}

function drawdown(){
  const a = D.accounts[state.account];
  let idx=1, peak=1; const dd=[];
  a.years.forEach(y=>{ idx*=(1+y.twr); peak=Math.max(peak,idx); dd.push([y.year, +((idx/peak-1)*100).toFixed(1)]); });
  charts.drawdown.setOption({
    tooltip:{trigger:'axis',valueFormatter:v=>v+'%'},
    grid:{left:48,right:16,top:16,bottom:28}, xAxis:{type:'category',data:dd.map(x=>x[0])},
    yAxis:{type:'value',max:0,axisLabel:{formatter:v=>v+'%'}},
    series:[{type:'line',data:dd.map(x=>x[1]),areaStyle:{color:'rgba(192,57,43,.15)'},lineStyle:{color:RED},itemStyle:{color:RED}}]
  });
}

function renderAll(){ cards(); youVsBench(); waterfall(); returns(); decomp(); cash(); drawdown(); }
window.addEventListener('resize', ()=>Object.values(charts).forEach(c=>c.resize()));
window.addEventListener('beforeprint', ()=>Object.values(charts).forEach(c=>c.resize()));
document.addEventListener('DOMContentLoaded', ()=>{
  ['vsbench','waterfall','returns','decomp','cash','drawdown'].forEach(mk);
  const bar = document.getElementById('acctbar');
  D.order.forEach((id,i)=>{
    const b=document.createElement('button'); b.className='acct-btn'+(i===0?' on':''); b.textContent=id;
    b.onclick=()=>{ state.account=id; [...bar.children].forEach(x=>x.classList.toggle('on',x===b)); renderAll(); };
    bar.appendChild(b);
  });
  renderAll();
  window.__charts_ready = true;
});
