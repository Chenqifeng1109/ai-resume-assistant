window.onerror=function(m,u,l){document.getElementById("wsStatus").textContent="ERR:"+m+" L"+l};
var stepsData=[{id:1,name:"简历解析",icon:"file-text",status:"done",detail:"上传/解析/删除"},{id:2,name:"智能优化简历",icon:"sparkles",status:"done",detail:"DeepSeek AI优化"},{id:3,name:"简历模板",icon:"layout",status:"done",detail:"6套模板+证件照"},{id:4,name:"岗位采集",icon:"search",status:"done",detail:"51前程无忧/采集历史"},{id:5,name:"JD匹配度评分",icon:"target",status:"done",detail:"AI打分"},{id:6,name:"精准简历优化",icon:"sparkles",status:"done",detail:"JD定向优化"},{id:7,name:"自动打招呼",icon:"send",status:"done",detail:"半自动投递"}];
function L(t,l,m){}function slideInCenter(){var b=document.getElementById("centerBody");b.classList.remove("flip-in","slide-up");void b.offsetWidth;b.classList.add("flip-in")}function goHome(){viewingDetail=false;sessionStorage.setItem("activeStep",0);var b=document.getElementById("centerBody");var cur=activeStepId;activeStepId=0;renderSteps();function showStep(i){if(i<=0){b.classList.remove("flip-in","slide-up");b.style.transition="transform .5s cubic-bezier(0.16,1,0.3,1),opacity .35s ease";b.style.transform="translateY(60px)";b.style.opacity="0";setTimeout(function(){b.innerHTML=welcomeHTML;document.getElementById("centerTitle").textContent="AI 智能简历助手";document.getElementById("centerSubtitle").textContent="让你的求职效率翻倍";void b.offsetWidth;b.style.transform="translateY(0)";b.style.opacity="1";R()},120);return}activeStepId=i;renderSteps();renderCenter();slideInCenter();setTimeout(function(){showStep(i-1)},500)}showStep(cur)};var statsData={resumes:0,jobs_found:0,deliveries:0},activeStepId=6,viewingDetail=false;
(function(){var c=document.getElementById("particleCanvas"),x=c.getContext("2d");c.width=innerWidth;c.height=innerHeight;var p=[];for(var i=0;i<60;i++)p.push({x:Math.random()*c.width,y:Math.random()*c.height,s:Math.random()*2+0.5,dy:Math.random()*0.5+0.1});setInterval(function(){x.clearRect(0,0,c.width,c.height);p.forEach(function(a){a.y+=a.dy;if(a.y>c.height+5)a.y=-5;x.beginPath();x.arc(a.x,a.y,a.s,0,Math.PI*2);x.fillStyle="rgba(0,229,255,0.3)";x.fill()})},33)})();
function S(m,c){var e=document.getElementById("wsStatus");e.textContent=m;if(c)e.style.color=c}

function renderSteps(){var c=document.getElementById("stepsList");var icons={settings:"⚙️",folder:"📁",monitor:"🖥️","file-text":"📄",search:"🔍",target:"🎯",send:"📤","message-circle":"💬",database:"🗄️","bar-chart-2":"📊",file:"📜",calendar:"📅",layers:"📚",zap:"⚡",globe:"🌐",sparkles:"✨",layout:"📐"};c.innerHTML=stepsData.map(function(s,i){var act=s.id===activeStepId;var done=s.status==="done";var icon=icons[s.icon]||"●";var cls=act?"step-card active":done?"step-card done":"step-card";var check=done?'<span class="step-check">✔</span>':'';return'<div class="'+cls+'" data-id="'+s.id+'"><div class="step-card-icon">'+icon+'</div><div class="step-card-info"><div class="step-card-name">'+s.name+'</div><div class="step-card-detail">'+s.detail+'</div></div>'+check+'</div>'}).join("");c.querySelectorAll(".step-card").forEach(function(el){el.addEventListener("click",function(){activeStepId=parseInt(el.dataset.id);viewingDetail=false;sessionStorage.setItem("activeStep",activeStepId);renderSteps();renderCenter();slideInCenter()})})}function R(){var wR=document.getElementById("wResumes");if(wR)wR.textContent=statsData.resumes;var wJ=document.getElementById("wJobs");if(wJ)wJ.textContent=statsData.jobs_found;var wD=document.getElementById("wDelivered");if(wD)wD.textContent=statsData.deliveries||0;document.getElementById("statsBar").innerHTML='<span class="home-btn" onclick="goHome()">🏠</span><span>📄 '+statsData.resumes+'份</span><span>📋 '+statsData.jobs_found+'个</span>'}
function P(el,label,dur,onCancel){
  var id='pb'+Date.now();
  var h='<div id="'+id+'" style="padding:16px 20px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:12px">'
    +'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
    +'<span style="font-size:13px;font-weight:600;color:var(--accent)">'+(label||'DeepSeek三维评分')+'</span>'
    +'<span id="'+id+'_pct" style="font-size:12px;color:var(--text-dim)">0%</span></div>'
    +'<div style="height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;margin-bottom:6px">'
    +'<div id="'+id+'_fill" style="height:100%;width:0%;background:linear-gradient(90deg,var(--accent2),var(--accent));border-radius:3px;transition:width .3s linear"></div></div>'
    +'<div style="display:flex;justify-content:space-between;align-items:center">'
    +'<span id="'+id+'_eta" style="font-size:11px;color:var(--text-dim)">预计剩余: --s</span>'
    +(onCancel?'<button onclick="'+onCancel+'" style="background:none;border:1px solid #ff4081;color:#ff4081;padding:2px 10px;border-radius:4px;cursor:pointer;font-size:11px">取消</button>':'')
    +'</div></div>';
  el.innerHTML=h;
  var s=Date.now(),t=null;
  var f=function(p){
    var e=document.getElementById(id+'_fill');if(e)e.style.width=Math.min(p,95)+'%';
    var c=document.getElementById(id+'_pct');if(c)c.textContent=Math.round(p)+'%';
    var a=document.getElementById(id+'_eta');
    if(a&&p>0&&p<95){
      var r=((Date.now()-s)/p*(100-p)/1000).toFixed(0);
      a.textContent='预计剩余: '+Math.max(0,r)+'s';
    }else if(a&&p>=95){a.textContent='即将完成...';a.style.color='var(--accent)'}
  };
  var g=setInterval(function(){var p=Math.min(95,((Date.now()-s)/(dur||15000))*100);f(p)},300);
  return {
    update:f,
    done:function(){
      clearInterval(g);f(100);
      var c=document.getElementById(id+'_eta');if(c){c.textContent='✅ 完成';c.style.color='#0f0'}
      setTimeout(function(){var d=document.getElementById(id);if(d)d.style.opacity='0';setTimeout(function(){if(d)d.remove()},400)},600)
    },
    fail:function(msg){
      clearInterval(g);
      var c=document.getElementById(id+'_eta');if(c){c.textContent='❌ '+(msg||'失败');c.style.color='#ff4081'}
      var e=document.getElementById(id+'_fill');if(e)e.style.background='#ff4081'
    }
  }
}

function renderCenter(){
  if(viewingDetail)return;
  var s=stepsData.find(function(x){return x.id===activeStepId});if(!s||s.id===0)return;
  document.getElementById("centerTitle").textContent=s.name;
  document.getElementById("centerSubtitle").textContent=s.detail;
  var b=document.getElementById("centerBody");
  b.querySelectorAll(".card").forEach(function(c){c.remove()});
  if(s.id===1){b.innerHTML='<div class="card"><h3>简历解析引擎</h3><p style="color:var(--text-dim);margin-bottom:12px">上传简历，AI自动提取信息</p><input type="file" id="rf" accept=".docx,.pdf,.txt" style="display:none" onchange="uploadResume()"><button class="btn btn-primary" onclick="triggerUpload()">上传并解析简历</button></div><div id="rl"></div>';loadResumeList()}
    else if(s.id===2){b.innerHTML='<div class="card"><h3>✨ AI智能优化简历</h3><p style="color:var(--text-dim);margin-bottom:12px">基于DeepSeek AI，根据求职意向智能优化简历</p><div style="margin-bottom:12px"><select id="oresume" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:100%;max-width:400px;font-size:13px"><option value="">加载中...</option></select></div><div style="margin-bottom:12px"><input id="otarget" placeholder="求职意向(如:新媒体运营经理)" style="background:#111;border:1px solid var(--border);color:#fff;padding:8px 12px;border-radius:6px;width:100%;max-width:400px;font-size:13px"></div><div style="margin-bottom:12px"><textarea id="oextra" placeholder="额外要求(可选,如:突出AI工具使用经验)" style="width:100%;height:60px;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:#fff;padding:8px;border-radius:6px;font-size:13px;resize:vertical"></textarea></div><button class="btn btn-glow" onclick="optimizeResume()">🚀 开始AI优化</button><div id="oresult" style="margin-top:16px"></div>';loadOptResumes()}
    else if(s.id===3){b.innerHTML='<div class="card"><h3>📐 简历模板</h3><p style="color:var(--text-dim);margin-bottom:12px">选择模板风格，上传证件照，一键导出精美简历</p><div style="margin-bottom:12px"><select id="tresume" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:100%;max-width:300px;font-size:13px"><option value="">加载中...</option></select></div><div style="margin-bottom:16px;display:flex;gap:12px;flex-wrap:wrap"><label style="cursor:pointer;padding:14px 18px;border:2px solid var(--border);border-radius:10px;text-align:center;flex:1;min-width:100px"><input type="radio" name="tstyle" value="classic" checked onchange="previewTemplate()" style="display:none"><div style="font-size:24px;margin-bottom:4px">📄</div><div style="font-size:13px;color:#fff">经典商务</div><div style="font-size:11px;color:var(--text-dim)">稳重专业</div></label><label style="cursor:pointer;padding:14px 18px;border:2px solid var(--border);border-radius:10px;text-align:center;flex:1;min-width:100px"><input type="radio" name="tstyle" value="modern" onchange="previewTemplate()" style="display:none"><div style="font-size:24px;margin-bottom:4px">🎨</div><div style="font-size:13px;color:#fff">现代简约</div><div style="font-size:11px;color:var(--text-dim)">紫色渐变</div></label><label style="cursor:pointer;padding:14px 18px;border:2px solid var(--border);border-radius:10px;text-align:center;flex:1;min-width:100px"><input type="radio" name="tstyle" value="dual" onchange="previewTemplate()" style="display:none"><div style="font-size:24px;margin-bottom:4px">📊</div><div style="font-size:13px;color:#fff">双栏技能</div><div style="font-size:11px;color:var(--text-dim)">左栏展示</div></label><label style="cursor:pointer;padding:14px 18px;border:2px solid var(--border);border-radius:10px;text-align:center;flex:1;min-width:100px"><input type="radio" name="tstyle" value="elegant" onchange="previewTemplate()" style="display:none"><div style="font-size:24px;margin-bottom:4px">✨</div><div style="font-size:13px;color:#fff">极简优雅</div><div style="font-size:11px;color:var(--text-dim)">黑白灰调</div></label><label style="cursor:pointer;padding:14px 18px;border:2px solid var(--border);border-radius:10px;text-align:center;flex:1;min-width:100px"><input type="radio" name="tstyle" value="minimal" onchange="previewTemplate()" style="display:none"><div style="font-size:24px;margin-bottom:4px">🤍</div><div style="font-size:13px;color:#fff">极简留白</div><div style="font-size:11px;color:var(--text-dim)">干净清爽</div></label><label style="cursor:pointer;padding:14px 18px;border:2px solid var(--border);border-radius:10px;text-align:center;flex:1;min-width:100px"><input type="radio" name="tstyle" value="timeline" onchange="previewTemplate()" style="display:none"><div style="font-size:24px;margin-bottom:4px">⏳</div><div style="font-size:13px;color:#fff">时间线</div><div style="font-size:11px;color:var(--text-dim)">经历轴展示</div></label></div><div style="margin-bottom:12px;display:flex;gap:12px;align-items:center"><span style="color:var(--text-dim);font-size:12px">证件照:</span><input type="file" id="tphoto" accept=".jpg,.jpeg,.png" style="display:none" onchange="uploadPhoto()"><button class="btn" onclick="document.getElementById(\'tphoto\').click()" style="border-color:var(--accent2);color:var(--accent2);font-size:12px;padding:6px 14px">📷 上传照片</button><span id="tphotoStatus" style="font-size:11px;color:var(--text-dim)"></span></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px"><button class="btn btn-glow" onclick="previewTemplate()">👁 预览</button><button class="btn btn-primary" onclick="downloadTemplate(\'html\')">📥 HTML</button><button class="btn btn-primary" onclick="downloadTemplate(\'pdf\')">📄 PDF</button></div><div id="tpreview" style="border:1px solid var(--border);border-radius:8px;overflow:hidden;min-height:200px;background:#fff"></div>';loadTemplateResumes()}
  else if(s.id===4){scrapeRunning=false;b.innerHTML='<div class="card"><h3>岗位采集</h3><p style="color:var(--text-dim);margin-bottom:4px">城市: 广州 | 根据简历求职意向精准采集</p><p id="scrapeTarget" style="color:var(--accent);font-size:13px;margin-bottom:12px">选择简历后将自动匹配求职岗位</p><div style="margin-bottom:12px"><select id="rs5" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:100%;max-width:300px;font-size:13px"><option value="">加载中...</option></select></div><div style="display:flex;gap:16px;margin-bottom:12px"><label style="display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--accent)"><input type="checkbox" class="pcb" value="51job" checked><span>51前程无忧</span></label></div><div style="margin-bottom:12px"><span style="color:var(--text-dim);font-size:12px">期望薪资:</span><input id="sala" type="text" placeholder="如 5k-8k" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:150px;font-size:13px;margin-left:8px"></div><button class="btn btn-primary" onclick="triggerScrape()">开始采集</button></div><div id="jl"></div>';loadOpts5();loadJobsList();loadJobsList()}
  else if(s.id===5){b.innerHTML='<div class="card"><h3>🎯 JD匹配度评分</h3><p style="color:var(--text-dim);margin-bottom:12px">粘贴岗位描述，AI评估匹配度</p><div style="margin-bottom:12px"><select id="jds" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:100%;max-width:300px;font-size:13px"><option value="">加载中...</option></select></div><textarea id="jdt" placeholder="粘贴岗位描述(JD)到这里..." style="width:100%;height:150px;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:#fff;padding:12px;border-radius:8px;font-size:13px;resize:vertical;font-family:inherit"></textarea><button class="btn btn-primary" onclick="runJDMatch()" style="margin-top:12px">开始匹配分析</button><div id="jdr" style="margin-top:16px"></div></div><div class="card" style="margin-top:16px"><h3>📊 批量JD匹配</h3><p style="color:var(--text-dim);margin-bottom:8px">对采集的岗位一键全量AI评分（三维：技能/经验/学历）</p><div style="margin-bottom:12px"><select id="brs" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:100%;max-width:300px;font-size:13px"><option value="">加载中...</option></select></div><div style="margin-bottom:12px"><select id="bjs" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:100%;max-width:300px;font-size:13px"><option value="">选择采集记录...</option></select></div><div style="margin-bottom:12px;display:flex;align-items:center;gap:8px"><span style="color:var(--text-dim);font-size:12px">阈值:</span><input id="sth" type="number" value="70" min="0" max="100" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:80px;font-size:13px"></div><button class="btn btn-glow" onclick="runBatchScore()">⚡ 一键全量匹配</button><div id="bsr" style="margin-top:16px"></div></div>';loadJDOpts();loadBatchOpts()}
  else if(s.id===6){b.innerHTML=renderPrecisionUI()}else if(s.id===7){b.innerHTML='<div class="card"><h3>📤 自动打招呼 & 投递</h3><p style="color:var(--text-dim);margin-bottom:12px">半自动模式：登录后逐条打开详情页，人工确认发送</p>'
    +'<div style="margin-bottom:16px;display:flex;gap:12px">'
    +'<div style="padding:10px 14px;background:rgba(255,171,0,0.08);border:1px solid rgba(255,171,0,0.25);border-radius:8px;margin-bottom:8px;font-size:13px;color:#ffab00;display:flex;align-items:center;gap:8px">⚠️ 请自行登录招聘平台后再使用打招呼功能 <button class="btn" onclick="openLogin51()" style="border-color:var(--accent2);color:var(--accent2);font-size:11px;padding:2px 10px;margin-left:auto;flex-shrink:0">🔑 打开51前程无忧</button></div>'
    +'</div>'
    +'<div style="margin-bottom:12px;display:flex;gap:12px;align-items:center">'
    +'<select id="dJobsFile" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;font-size:13px"><option value="">选择采集记录...</option></select>'
    +'<select id="dResume" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;font-size:13px"><option value="">选择简历</option></select>'
    +'<span style="color:var(--text-dim);font-size:12px">阈值:</span><input id="dTh" type="number" value="70" min="0" max="100" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:70px;font-size:13px">'
    +'<button class="btn btn-primary" onclick="loadDeliverCandidates()" style="font-size:13px">🔍 筛选</button>'
    +'</div>'
    +'<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px"><button class="btn" onclick="generateGreeting()" style="border-color:var(--accent2);color:var(--accent2);font-size:12px;padding:4px 12px">🤖 AI生成开场白</button><input id="gdirection" placeholder="方向(可选，留空自动生成)" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;font-size:12px;flex:1"></div>'
    +'<textarea id="dGreeting" placeholder="点击「🤖 AI生成开场白」自动填写..." style="width:100%;height:100px;background:rgba(255,255,255,0.05);border:1px solid var(--border);color:#fff;padding:10px;border-radius:8px;font-size:13px;resize:vertical;font-family:inherit;margin-bottom:8px"></textarea><button class="btn" onclick="copyGreeting()" style="margin-top:6px;border-color:var(--accent2);color:var(--accent2);font-size:12px;padding:4px 12px">📋 复制开场白</button>'
    +'<div id="dList" style="max-height:55vh;overflow-y:auto"><p style="color:var(--text-dim);text-align:center;padding:20px">选择采集结果和简历后点击「筛选」加载匹配岗位</p></div></div>';(async function(){try{var r=await fetch('/api/jobs/list');var d=await r.json();var sel=document.getElementById('dJobsFile');if(sel&&d.files&&d.files.length>0){sel.innerHTML='<option value="">选择采集记录...</option>'+d.files.map(function(f,i){var n=d.files.length-i;return '<option value="'+f.filename+'">第'+n+'次采集 · '+(f.keywords&&f.keywords[0]?f.keywords[0]:'未知')+' · '+f.count+'个岗位</option>'}).join('');if(d.files[0])sel.value=d.files[0].filename}}catch(e){}try{var r2=await fetch('/api/resumes/list');var d2=await r2.json();var sel2=document.getElementById('dResume');if(sel2&&d2.resumes){sel2.innerHTML='<option value="">选择简历...</option>'+d2.resumes.map(function(x){return '<option value="'+x.filename+'">'+x.name+(x.position?' - '+x.position:'')+'</option>'}).join('')}}catch(e){}})()}
  
}


async function generateGreeting(){
  var rf=document.getElementById("dResume").value;
  if(!rf){alert("请先选择简历");return}
  var dir=document.getElementById("gdirection").value.trim();
  var ta=document.getElementById("dGreeting");
  ta.value="AI正在生成...";
  ta.style.color="var(--accent)";
  try{
    var fd=new FormData();fd.append("resume_file",rf);fd.append("direction",dir);
    var r=await fetch("/api/deliver/greeting",{method:"POST",body:fd});
    var d=await r.json();
    if(d.ok){ta.value=d.greeting;ta.style.color="#fff";L(new Date().toLocaleTimeString(),"success","AI开场白已生成")}
    else{ta.value="生成失败: "+d.error;ta.style.color="#ff4081"}
  }catch(e){ta.value="网络错误: "+e.message;ta.style.color="#ff4081"}
}
async function loadDeliverOpts(){
  try{
    var r=await fetch("/api/jobs/list");
    var d=await r.json();
    var sel=document.getElementById("dJobsFile");
    if(sel&&d.files&&d.files.length>0){
      sel.innerHTML='<option value="">选择采集记录...</option>'+d.files.map(function(f,i){
        var n=d.files.length-i;
        return '<option value="'+f.filename+'">第'+n+'次采集 · '+(f.keywords&&f.keywords[0]?f.keywords[0]:'未知')+' · '+f.count+'个岗位</option>'
      }).join("");
      if(d.files[0])sel.value=d.files[0].filename
    }
  }catch(e){}
  try{
    var r2=await fetch("/api/resumes/list");
    var d2=await r2.json();
    var sel2=document.getElementById("dResume");
    if(sel2&&d2.resumes){
      sel2.innerHTML='<option value="">选择简历...</option>'+d2.resumes.map(function(x){
        return '<option value="'+x.filename+'">'+x.name+(x.position?' - '+x.position:'')+'</option>'
      }).join("")
    }
  }catch(e){}
}
function goToStep5(){activeStepId=5;renderSteps();renderCenter();slideInCenter()}
async function loadDeliverCandidates(){
  var jf=document.getElementById("dJobsFile").value;
  var rf=document.getElementById("dResume").value;
  var th=parseInt(document.getElementById("dTh").value)||70;
  var el=document.getElementById("dList");
  if(!jf||!rf){el.innerHTML='<div style="text-align:center;padding:40px;color:#ffab00"><p style="font-size:16px">⚠️ 你还没有选择采集记录或简历</p><p style="font-size:13px;color:var(--text-dim)">请在上方下拉菜单中选择后再点击「筛选」</p></div>';return}
  var _pb=P(el,'加载候选人列表',8000);
  try{
    var fd=new FormData();
    fd.append("jobs_file",jf);fd.append("resume_file",rf);fd.append("threshold",th);
    var r=await fetch("/api/deliver/list",{method:"POST",body:fd});
    var d=await r.json();
    if(d.ok){
      if(d.jobs&&d.jobs.length>0){
        var h='<p style="color:var(--text-dim);font-size:12px;margin-bottom:12px">共 '+d.total_jobs+' 个岗位, 符合阈值 '+d.candidates+' 个 (已投递 '+d.already_delivered+' 个排除)</p>';
        d.jobs.forEach(function(j,i){
          var sc=j.match_score||0;
          var scColor=sc>=75?"#0f0":sc>=50?"#ffab00":"#ff4081";
          h+='<div class="job-card" style="margin-bottom:8px;padding:12px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:10px;display:flex;align-items:center;gap:12px">';
          h+='<div style="min-width:42px;height:42px;border-radius:50%;background:radial-gradient(circle,'+scColor+'33,transparent 70%);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;color:'+scColor+'">'+sc+'</div>';
          h+='<div style="flex:1;min-width:0"><div style="font-size:14px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+j.title+'</div><div style="font-size:11px;color:var(--text-dim)">'+j.company+' · '+j.salary+' · '+j.location+'</div></div>';
          h+='<button class="btn" data-url="'+j.url+'" onclick="openJobDetailFromBtn(this)" style="border-color:var(--accent);color:var(--accent);font-size:12px;padding:6px 14px;flex-shrink:0">打开详情</button>';
          h+='';
          h+='</div>';
        });
        el.innerHTML=h
      }else{el.innerHTML='<div style="text-align:center;padding:40px;color:var(--text-dim)">没有符合条件的岗位(>= '+th+'分)，可降低阈值重试。提示：先在步骤5进行批量评分</div>'}
    }else{var isME=d.error.indexOf('步骤5')>=0;el.innerHTML='<div style="text-align:center;padding:40px;color:#ff4081">'+d.error+(isME?'<br><br><button class="btn btn-primary" onclick="goToStep5()" style="font-size:14px;padding:10px 28px">🎯 前往步骤5: JD匹配度评分</button>':'')+'</div>'}
  }catch(e){el.innerHTML='<div style="text-align:center;padding:40px;color:#ff4081">加载失败: '+e.message+'</div>'}
}
function openLogin51(){window.location.href="https://we.51job.com/"}
function openJobDetail(url){if(url)window.location.href=url}
function openJobDetailFromBtn(btn){var u=btn.getAttribute("data-url");if(u)window.location.href=u}
function copyGreeting(){
  var el=document.getElementById("dGreeting");
  if(el){
    el.select();
    document.execCommand("copy");
    L(new Date().toLocaleTimeString(),"success","打招呼文案已复制")
  }
}

function openLogin51(){window.location.href="https://we.51job.com/"}
function openJobDetail(url){if(url)window.location.href=url}
function openJobDetailFromBtn(btn){var u=btn.getAttribute("data-url");if(u)window.location.href=u}

function triggerUpload(){var el=document.getElementById("rf");if(el)el.click()}
async function loadResumeList(){try{var r=await fetch("/api/resumes/list");var d=await r.json();var el=document.getElementById("rl");if(!el)return;if(d.resumes&&d.resumes.length>0){el.innerHTML='<div class="card"><h3>已解析('+d.count+'份)</h3>'+d.resumes.map(function(x){return '<div data-fn="'+x.filename+'" style="padding:10px;margin:4px 0;border-radius:8px;background:rgba(255,255,255,0.03);border:1px solid var(--border);display:flex;justify-content:space-between;align-items:center"><div style="cursor:pointer;flex:1" onclick="viewResume(\''+x.filename+'\')" onmouseover="this.style.color=\'var(--accent)\'" onmouseout="this.style.color=\'\'"><span style="color:var(--accent);font-weight:600">'+x.name+'</span>'+ (x.position?' <span style="color:var(--accent2);font-size:12px">🎯 '+x.position+'</span>':'') +'<br><span style="font-size:11px;color:var(--text-dim)">'+x.parsed_at+'</span></div><button onclick="event.stopPropagation();deleteResume(\''+x.filename+'\')" style="background:none;border:1px solid #ff4081;color:#ff4081;padding:4px 12px;border-radius:6px;cursor:pointer;font-size:11px">删除</button></div>'}).join("")+'</div>'}}catch(e){}}
async function loadOpts5(){try{var r=await fetch("/api/resumes/list");var d=await r.json();var sel=document.getElementById("rs5");if(!sel)return;sel.innerHTML='<option value="">选择简历...</option>'+d.resumes.map(function(x){return '<option value="'+x.filename+'" data-salary="'+(x.desired_salary||'')+'" data-position="'+(x.position||'')+'">'+x.name+(x.position?' - '+x.position:'')+'</option>'}).join("");sel.onchange=function(){var opt=sel.options[sel.selectedIndex];var s=opt.getAttribute('data-salary')||'';var p=opt.getAttribute('data-position')||'';var inp=document.getElementById('sala');if(inp&&s){inp.value=s}var tp=document.getElementById('scrapeTarget');if(tp){tp.textContent=p?'采集目标: '+p:'选择简历后将自动匹配求职岗位';tp.style.color=p?'var(--accent)':'var(--text-dim)'}};var opt0=sel.options[0];if(opt0){var s0=opt0.getAttribute('data-salary');if(s0){var inp=document.getElementById('sala');if(inp)inp.placeholder=s0||inp.placeholder}}}catch(e){}}
async function loadJobsList(){try{var r=await fetch("/api/jobs/list");var d=await r.json();var el=document.getElementById("jl");if(!el)return;if(d.files&&d.files.length>0){var latest=d.files.slice(0,5);var total=d.files.length;el.innerHTML='<div class="card"><h3>采集历史 (最近5次/共'+total+'次)</h3>'+latest.map(function(f,i){var n=total-i;return '<div data-fn="'+f.filename+'" onclick="viewJobs(\''+f.filename+'\')" style="padding:10px;margin:4px 0;border-radius:8px;cursor:pointer;background:rgba(255,255,255,0.03);border:1px solid var(--border)" onmouseover="this.style.background=\'rgba(0,229,255,0.06)\'" onmouseout="this.style.background=\'rgba(255,255,255,0.03)\'"><span style="color:var(--accent)">第'+n+'次采集</span> <span style="font-size:11px;color:var(--text-dim)">'+(f.keywords&&f.keywords[0]?f.keywords[0]:'未知')+'</span> · <span style="font-size:11px;color:var(--text-dim)">'+f.count+'个岗位</span></div>'}).join("")+'</div>'}}catch(e){}}
async function loadJDOpts(){try{var r=await fetch("/api/resumes/list");var d=await r.json();var sel=document.getElementById("jds");if(!sel)return;sel.innerHTML='<option value="">请选择简历</option>'+d.resumes.map(function(x){return '<option value="'+x.filename+'">'+x.name+(x.position?' - '+x.position:'')+'</option>'}).join("")}catch(e){}}
async function loadBatchOpts(){try{var r=await fetch("/api/resumes/list");var d=await r.json();var sel=document.getElementById("brs");if(!sel)return;sel.innerHTML='<option value="">请选择简历</option>'+d.resumes.map(function(x){return '<option value="'+x.filename+'">'+x.name+(x.position?' - '+x.position:'')+'</option>'}).join("")}catch(e){};try{var r2=await fetch("/api/jobs/list");var d2=await r2.json();var sel2=document.getElementById("bjs");if(!sel2)return;if(d2.files&&d2.files.length>0){sel2.innerHTML='<option value="">选择采集记录...</option>'+d2.files.map(function(f,i){var n=d2.files.length-i;return '<option value="'+f.filename+'">第'+n+'次采集 · '+(f.keywords&&f.keywords[0]?f.keywords[0]:'未知')+' · '+f.count+'个岗位</option>'}).join("");sel2.value=d2.files[0].filename}}catch(e){}}
async function startScrape(){if(scrapeRunning){alert("采集正在进行中");return}var cbs=document.querySelectorAll(".pcb:checked");if(cbs.length===0){alert("请选择平台");return}var platforms=Array.from(cbs).map(function(c){return c.value}).join(",");var sel=document.getElementById("rs5");var rf=sel?sel.value:"";if(!rf){alert("请先选择一份简历，系统将根据求职意向精准采集");return}L(new Date().toLocaleTimeString(),"info","启动采集: "+platforms);try{var fd=new FormData();fd.append("platforms",platforms);fd.append("resume_file",rf);var sr=document.getElementById("sala");if(sr&&sr.value.trim())fd.append("salary_range",sr.value.trim());var r=await fetch("/api/jobs/scrape",{method:"POST",body:fd});var d=await r.json();if(d.ok){L(new Date().toLocaleTimeString(),"success","采集已启动");scrapeRunning=true;pollStatus()}else{L(new Date().toLocaleTimeString(),"error",d.error||"启动失败")}}catch(e){L(new Date().toLocaleTimeString(),"error","启动失败")}}
function triggerScrape(){startScrape()}
async function pollStatus(){var c=0;while(c<180){await new Promise(function(r){setTimeout(r,2000)});try{var r=await fetch("/api/jobs/scrape/status");var s=await r.json();if(!s.running){scrapeRunning=false;L(new Date().toLocaleTimeString(),"success","完成! "+s.jobs_count+"个");loadJobsList();return}if(c%5===0)L(new Date().toLocaleTimeString(),"info","采集中: "+s.progress)}catch(e){}c++}scrapeRunning=false}
async function runJDMatch(){var jd=document.getElementById("jdt").value.trim();if(jd.length<10){alert("请粘贴岗位描述(至少10字)");return}var sel=document.getElementById("jds");var rf=sel?sel.value:"";var rd=document.getElementById("jdr");if(!rf){rd.innerHTML='<div class="card" style="text-align:center;padding:40px"><p style="color:#ffab00;font-size:16px">⚠️ 你还没有选择简历</p><p style="color:var(--text-dim);font-size:13px">请在下方下拉菜单中选择一份简历</p></div>';return}var _pb4=P(rd,'DeepSeek三维评分',12000);try{var fd=new FormData();fd.append("jd_text",jd);fd.append("resume_file",rf);var r=await fetch("/api/jd/match",{method:"POST",body:fd});var d=await r.json();if(d.ok){var sc=d.overall_score||0;var sk=d.skill_match||0;var ex=d.experience_match||0;var ed=d.education_match||0;var cc=sc>=75?"#0f0":sc>=50?"#ffab00":"#ff4081";var h='<div class="card"><h3>匹配度分析</h3><div style="text-align:center;margin:16px 0"><div style="font-size:52px;font-weight:800;color:'+cc+'">'+sc+'/100</div></div><div style="display:flex;gap:12px;margin-bottom:16px">'+scoreBar("技能匹配",sk)+scoreBar("经验匹配",ex)+scoreBar("学历匹配",ed)+'</div>';if(d.verdict)h+='<div style="padding:10px 14px;background:rgba(0,229,255,0.06);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;margin-bottom:12px;font-size:14px">💬 '+d.verdict+'</div>';if(d.strengths&&d.strengths.length>0){h+='<div style="margin-bottom:8px"><b style="color:#0f0">✅ 匹配优势</b>';d.strengths.forEach(function(s){h+='<div style="font-size:13px;color:var(--text-dim);padding:2px 0">• '+s+'</div>'});h+='</div>'}if(d.weaknesses&&d.weaknesses.length>0){h+='<div style="margin-bottom:8px"><b style="color:#ffab00">⚠️ 不足之处</b>';d.weaknesses.forEach(function(w){h+='<div style="font-size:13px;color:var(--text-dim);padding:2px 0">• '+w+'</div>'});h+='</div>'}if(d.suggestions&&d.suggestions.length>0){h+='<div><b style="color:var(--accent)">💡 建议</b>';d.suggestions.forEach(function(s){h+='<div style="font-size:13px;color:var(--text-dim);padding:2px 0">• '+s+'</div>'});h+='</div>'}h+='</div>';rd.innerHTML=h}else{rd.innerHTML='<div class="card"><p style="color:#ff4081">'+d.error+'</p></div>'}}catch(e){rd.innerHTML='<div class="card"><p style="color:#ff4081">'+e.message+'</p></div>'}}
async function runBatchScore(){var jf=document.getElementById("bjs").value;if(!jf){alert("请选择采集结果");return}var rf=document.getElementById("brs").value;var th=parseInt(document.getElementById("sth").value)||70;var rd=document.getElementById("bsr");rd.innerHTML='<div class="card" style="text-align:center;padding:40px"><h3 style="color:var(--accent);margin-bottom:12px">AI 批量分析中...</h3><p style="color:var(--text-dim);font-size:13px;margin-bottom:20px">DeepSeek 三维评分</p><div style="width:80%;max-width:400px;height:8px;background:rgba(255,255,255,0.06);border-radius:10px;margin:0 auto 16px;overflow:hidden"><div id="batchProgressBar" style="width:2%;height:100%;background:linear-gradient(90deg,var(--accent),#a78bfa);border-radius:10px;animation:progressPulse 1.5s ease-in-out infinite"></div></div><p id="batchEstTime" style="color:var(--text-dim);font-size:12px">预计还需 ~15 秒...</p></div>';var bpBar=document.getElementById("batchProgressBar");var bpEst=document.getElementById("batchEstTime");var bpStart=Date.now();var bpTotal=15;var bpInterval=setInterval(function(){var e=(Date.now()-bpStart)/1000;var s=Math.max(1,Math.ceil(bpTotal-e));var p=Math.min(92,Math.floor(e/bpTotal*100));if(bpBar)bpBar.style.width=p+"%";if(bpEst)bpEst.textContent="预计还需 ~"+s+" 秒..."},600);try{var r=await fetch("/api/jobs/batch-score-json",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({jobs_file:jf,resume_file:rf,threshold:th})});var d=await r.json();clearInterval(bpInterval);if(d.ok){var hi=d.jobs.filter(function(j){return (j.match_score||0)>=th});var lo=d.jobs.filter(function(j){return (j.match_score||0)<th});var h='<div class="card" style="padding:20px"><h3 style="font-size:20px;margin-bottom:4px">📊 批量匹配完成</h3><p style="color:var(--text-dim);font-size:13px">共 '+d.total+' 个岗位 · '+d.resume_name+'</p>';h+='<div style="display:flex;gap:12px;margin:20px 0">';h+='<div class="score-stat" style="flex:1;padding:16px;background:rgba(0,255,0,0.08);border:1px solid rgba(0,255,0,0.2);border-radius:12px;text-align:center;cursor:pointer" onclick="swT(0)"><div style="font-size:36px;font-weight:800;color:#0f0">'+hi.length+'</div><div style="color:var(--text-dim);font-size:12px;margin-top:4px">✅ ≥'+th+'分</div></div>';h+='<div class="score-stat" style="flex:1;padding:16px;background:rgba(255,64,129,0.08);border:1px solid rgba(255,64,129,0.2);border-radius:12px;text-align:center;cursor:pointer" onclick="swT(1)"><div style="font-size:36px;font-weight:800;color:#ff4081">'+lo.length+'</div><div style="color:var(--text-dim);font-size:12px;margin-top:4px">⚠️ <'+th+'分</div></div>';h+='</div>';h+='<div style="display:flex;gap:0;margin:0 0 16px 0;background:rgba(255,255,255,0.03);border-radius:10px;overflow:hidden">';h+='<div class="mtab active" onclick="swT(0)" style="flex:1;padding:10px;text-align:center;cursor:pointer;font-size:13px;font-weight:600">✅ 符合岗位</div>';h+='<div class="mtab" onclick="swT(1)" style="flex:1;padding:10px;text-align:center;cursor:pointer;font-size:13px;font-weight:600">⚠️ 未达标</div>';h+='</div>';h+='<div id="mp0" class="mpanel" style="max-height:60vh;overflow-y:auto">';if(hi.length>0){hi.forEach(function(j,i){h+=buildJobCard(j,j.match_score||50,j.skill_match||50,j.experience_match||50,j.education_match||50,(j.match_score||0)>=75?"#0f0":(j.match_score||0)>=50?"#ffab00":"#ff4081",i)})}else{h+='<div class="card" style="text-align:center;padding:40px;color:var(--text-dim)">没有达到阈值的岗位</div>'}h+='</div>';h+='<div id="mp1" class="mpanel" style="display:none;max-height:60vh;overflow-y:auto">';if(lo.length>0){lo.forEach(function(j,i){h+=buildJobCard(j,j.match_score||50,j.skill_match||50,j.experience_match||50,j.education_match||50,(j.match_score||0)>=50?"#ffab00":"#ff4081",i+hi.length)})}else{h+='<div class="card" style="text-align:center;padding:40px;color:#0f0">全部达标!</div>'}h+='</div></div>';rd.innerHTML=h}else{rd.innerHTML='<div class="card" style="text-align:center;padding:40px"><p style="color:#ff4081;font-size:16px">'+d.error+'</p><button class="btn-glow" onclick="runBatchScore()" style="margin-top:16px">🔄 重试</button></div>'}}catch(e){rd.innerHTML='<div class="card" style="text-align:center;padding:40px"><p style="color:#ff4081;font-size:16px">网络错误: '+e.message+'</p><button class="btn-glow" onclick="runBatchScore()" style="margin-top:16px">🔄 重试</button></div>'}}
function buildJobCard(j,sc,sk,ex,ed,scColor,idx){var card='<div class="job-card" id="jc'+idx+'" onclick="toggleCardDetail('+idx+')">';card+='<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">';card+='<div style="min-width:56px;height:56px;border-radius:50%;background:radial-gradient(circle,'+scColor+'33,transparent 70%);display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800;color:'+scColor+'">'+sc+'</div>';card+='<div style="flex:1;min-width:0"><div style="font-size:15px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+j.title+'</div>';card+='<div style="font-size:12px;color:var(--text-dim);margin-top:2px">'+j.company+' · '+j.salary+' · '+j.location+'</div></div>';card+='<div style="font-size:11px;color:var(--accent);cursor:pointer">▼ 详情</div></div>';card+='<div style="display:flex;gap:12px;margin-bottom:8px">'+scoreBarUI("技能",sk)+scoreBarUI("经验",ex)+scoreBarUI("学历",ed)+'</div>';card+='<div id="jd'+idx+'" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">';if(j.match_brief)card+='<div style="margin-bottom:10px;padding:8px 12px;background:rgba(0,229,255,0.06);border-left:3px solid var(--accent);border-radius:0 6px 6px 0;font-size:13px">💬 '+j.match_brief+'</div>';if(j.strengths&&j.strengths.length>0){card+='<div style="margin-bottom:8px"><span style="color:#0f0;font-size:12px;font-weight:600">✅ 匹配优势</span>';j.strengths.forEach(function(s){card+='<div style="font-size:12px;color:var(--text-dim);padding:2px 0">• '+s+'</div>'});card+='</div>'}if(j.weaknesses&&j.weaknesses.length>0){card+='<div style="margin-bottom:8px"><span style="color:#ffab00;font-size:12px;font-weight:600">⚠️ 不足之处</span>';j.weaknesses.forEach(function(w){card+='<div style="font-size:12px;color:var(--text-dim);padding:2px 0">• '+w+'</div>'});card+='</div>'}if(j.suggestions&&j.suggestions.length>0){card+='<div><span style="color:var(--accent);font-size:12px;font-weight:600">💡 建议</span>';j.suggestions.forEach(function(s){card+='<div style="font-size:12px;color:var(--text-dim);padding:2px 0">• '+s+'</div>'});card+='</div>'}card+='</div></div>';return card}
function scoreBarUI(label,val){var c=val>=75?"#0f0":val>=50?"#ffab00":"#ff4081";return '<div style="flex:1"><div style="font-size:10px;color:var(--text-dim);margin-bottom:3px">'+label+'</div><div style="height:6px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden"><div style="height:100%;width:'+val+'%;background:'+c+';border-radius:3px;transition:width 1s ease"></div></div><div style="font-size:10px;color:'+c+';text-align:right;margin-top:2px">'+val+'</div></div>'}
function scoreBar(label,val){return scoreBarUI(label,val)}
function toggleCardDetail(idx){var el=document.getElementById("jd"+idx);if(el)el.style.display=el.style.display==="none"?"block":"none"}
function swT(n){document.querySelectorAll(".mtab").forEach(function(t,i){t.classList.toggle("active",i===n)});var p0=document.getElementById("mp0");var p1=document.getElementById("mp1");if(p0)p0.style.display=n===0?"block":"none";if(p1)p1.style.display=n===1?"block":"none"}
function viewResume(fn){var _prevStep=activeStepId;viewingDetail=true;fetch("/api/resumes/detail/"+fn).then(function(r){return r.json()}).then(function(d){if(d.ok){var x=d.data;var b=document.getElementById("centerBody");b.querySelectorAll(".card").forEach(function(c){c.remove()});document.getElementById("centerTitle").textContent="📄 "+x.name;var h='<div class="card" style="overflow-y:auto;max-height:70vh"><h3>'+x.name+'</h3>';if(x.desired_position)h+='<div style="margin:10px 0;padding:10px;background:rgba(0,229,255,0.05);border-left:3px solid var(--accent);border-radius:0 8px 8px 0"><b style="color:var(--accent)">🎯 求职意向：</b>'+x.desired_position+'</div>';if(x.desired_salary)h+='<div style="margin:8px 0;color:var(--accent2)">💰 期望薪资：'+x.desired_salary+'</div>';h+='<div style="margin:12px 0"><h4 style="color:var(--text-dim);border-bottom:1px solid var(--border);padding-bottom:4px">📋 基本信息</h4>';if(x.phone)h+='<p>📱 电话：'+x.phone+'</p>';if(x.email)h+='<p>📧 邮箱：'+x.email+'</p>';if(x.education&&x.education.length>0){h+='<p>🎓 学历：';x.education.forEach(function(e){h+=e.school+' | '+e.major+' | '+e.degree+' | '+e.year+'<br>'});h+='</p>'}h+='</div>';if(x.work_experience&&x.work_experience.length>0){h+='<div style="margin:12px 0"><h4 style="color:var(--text-dim);border-bottom:1px solid var(--border);padding-bottom:4px">💼 工作/实习经历</h4>';x.work_experience.forEach(function(w){h+='<div style="margin:8px 0;padding:8px 12px;background:rgba(255,255,255,0.02);border-radius:6px"><b>'+w.position+'</b> @ '+w.company+' <span style="color:var(--text-dim);font-size:11px">'+w.duration+'</span>';if(w.description)h+='<p style="margin-top:4px;color:var(--text-dim);font-size:13px">'+w.description+'</p>';h+='</div>'});h+='</div>'}if(x.skills&&x.skills.length>0){h+='<div style="margin:12px 0"><h4 style="color:var(--text-dim);border-bottom:1px solid var(--border);padding-bottom:4px">🛠 技能</h4><div style="display:flex;flex-wrap:wrap;gap:8px">';x.skills.forEach(function(s){h+='<span style="padding:4px 12px;background:rgba(124,77,255,0.1);border:1px solid var(--accent2);border-radius:20px;font-size:12px">'+s+'</span>'});h+='</div></div>'}if(x.summary)h+='<div style="margin:12px 0"><h4 style="color:var(--text-dim);border-bottom:1px solid var(--border);padding-bottom:4px">📝 综合摘要</h4><p style="color:var(--text-dim);white-space:pre-wrap">'+x.summary+'</p></div>';h+='<button class="btn" onclick="backFromDetail()" style="margin-top:16px;width:100%;border-color:var(--accent2);color:var(--accent2)">⬅ 返回列表</button></div>';b.innerHTML=h}})}
async function deleteResume(fn){if(!confirm("确定删除 "+fn+" ?"))return;try{var r=await fetch("/api/resumes/delete/"+fn,{method:"DELETE"});var d=await r.json();if(d.ok){L(new Date().toLocaleTimeString(),"success","已删除: "+fn);sessionStorage.setItem("activeStep",activeStepId);setTimeout(function(){location.reload()},400)}else{L(new Date().toLocaleTimeString(),"error","删除失败: "+d.error)}}catch(e){L(new Date().toLocaleTimeString(),"error","删除错误: "+e.message)}}
async function viewJobs(fn){
  var _prevStep=activeStepId;
  viewingDetail=true;
  var b=document.getElementById("centerBody");
  P(b,'加载采集详情',6000);
  document.getElementById("centerTitle").textContent="📋 采集详情";
  try{
    var r=await fetch("/api/jobs/detail/"+encodeURIComponent(fn));
    var d=await r.json();
    if(d.ok&&d.data){
      var jobs=d.data.jobs||[];
      var collected=d.data.collected_at||"";
      var keywords=d.data.keywords||[];
      var h='<div class="card" style="overflow-y:auto;max-height:65vh">';
      h+='<h3>📋 本次采集共 '+jobs.length+' 个岗位</h3>';
      h+='<p style="color:var(--text-dim);font-size:12px;margin-bottom:8px">时间: '+collected+'</p>';
      if(keywords.length>0)h+='<p style="color:var(--text-dim);font-size:12px;margin-bottom:12px">搜索关键词: '+keywords.join(", ")+'</p>';
      jobs.forEach(function(j,i){
        h+='<div class="job-card" style="margin-bottom:10px;padding:14px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:10px">';
        h+='<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">';
        h+='<span style="min-width:28px;height:28px;border-radius:50%;background:var(--accent2);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff">'+(i+1)+'</span>';
        h+='<div style="flex:1"><div style="font-size:15px;font-weight:600;color:#fff">'+j.title+'</div>';
        h+='<div style="font-size:12px;color:var(--text-dim)">'+j.company+' · '+j.salary+' · '+j.location+'</div></div></div>';
        if(j.experience||j.education){
          h+='<div style="font-size:11px;color:var(--text-dim);margin-bottom:6px">';
          if(j.experience)h+='📅 经验: '+j.experience+'  ';
          if(j.education)h+='🎓 学历: '+j.education;
          h+='</div>';
        }
        if(j.tags&&j.tags.length>0){
          var seen={};
          var uniqueTags=[];
          j.tags.forEach(function(t){
            var items=t.split(/[\n\r]+/).filter(function(x){return x.trim()});
            items.forEach(function(item){
              var clean=item.trim();
              if(clean&&!seen[clean]){seen[clean]=true;uniqueTags.push(clean);}
            });
          });
          var displayTags=uniqueTags.slice(0,20);
          h+='<div style="font-size:10px;color:var(--text-dim);margin-bottom:4px">🏷️ 岗位要求/关键词:</div>';
          h+='<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px">';
          displayTags.forEach(function(t){
            h+='<span style="padding:3px 10px;background:rgba(124,77,255,0.1);border:1px solid rgba(124,77,255,0.2);border-radius:12px;font-size:11px;color:var(--accent2)">'+t+'</span>';
          });
          if(uniqueTags.length>20)h+='<span style="font-size:11px;color:var(--text-dim)">...等'+uniqueTags.length+'个</span>';
          h+='</div>';
        }
        h+='</div>';
      });
      h+='<button class="btn" onclick="backFromDetail()" style="margin-top:16px;width:100%;border-color:var(--accent2);color:var(--accent2)">⬅ 返回</button></div>';
      b.innerHTML=h
    }else{
      b.innerHTML='<div class="card"><p style="color:var(--text-dim)">未找到采集记录</p><button class="btn" onclick="backFromDetail()">⬅ 返回</button></div>'
    }
  }catch(e){
    b.innerHTML='<div class="card"><p style="color:#ff4081">加载失败: '+e.message+'</p><button class="btn" onclick="backFromDetail()">⬅ 返回</button></div>'
  }
}function backFromDetail(){viewingDetail=false;var b=document.getElementById("centerBody");b.querySelectorAll(".card").forEach(function(c){c.remove()});if(typeof _prevStep!=="undefined")activeStepId=_prevStep;renderSteps();renderCenter()}





async function loadOptResumes(){
  try{var r=await fetch("/api/resumes/list");var d=await r.json();var sel=document.getElementById("oresume");
  if(!sel)return;sel.innerHTML='<option value="">选择简历...</option>'+d.resumes.map(function(x){
    return '<option value="'+x.filename+'">'+x.name+(x.position?" - "+x.position:"")+'</option>'
  }).join("")}catch(e){}
}
async function optimizeResume(){
  var rf=document.getElementById("oresume").value;
  var target=document.getElementById("otarget").value.trim();
  var extra=document.getElementById("oextra").value.trim();
  if(!rf){alert("请选择一份已解析的简历");return}
  if(!target){alert("请填写求职意向");return}
  var rd=document.getElementById("oresult");
  var _pb5=P(rd,'DeepSeek三维评分',18000);
  try{
    var fd=new FormData();fd.append("resume_file",rf);fd.append("target",target);fd.append("extra",extra);
    var r=await fetch("/api/resume/optimize",{method:"POST",body:fd});
    var d=await r.json();
    if(d.ok){
      var h='<div class="card"><h3>✨ 三维度优化结果</h3>';
      h+='<div style="margin:12px 0;padding:10px;background:rgba(0,229,255,0.05);border-left:3px solid var(--accent);border-radius:0 8px 8px 0"><b style="color:var(--accent)">求职意向: </b>'+d.target+'</div>';if(d.job_analysis)h+='<div style="margin:8px 0;padding:10px;background:rgba(255,171,0,0.05);border-left:3px solid var(--warning);border-radius:0 8px 8px 0;font-size:13px;color:var(--accent2);line-height:1.5">🔍 <b>岗位分析:</b> '+d.job_analysis+'</div>';
      if(d.optimized_summary)h+='<div style="margin:16px 0"><h4 style="color:var(--accent)">📝 优化后个人总结</h4><p style="color:#fff;white-space:pre-wrap;line-height:1.6">'+d.optimized_summary+'</p></div>';
      if(d.optimized_projects&&d.optimized_projects.length>0){h+='<div style="margin:16px 0"><h4 style="color:var(--accent2)">🚀 优化项目经验</h4>';d.optimized_projects.forEach(function(p){h+='<div style="margin:8px 0;padding:12px;background:rgba(0,255,136,0.05);border-left:3px solid var(--accent2);border-radius:0 8px 8px 0"><b>'+p.name+'</b> — <span style="color:var(--text-dim);font-size:13px">'+p.role+'</span><p style="font-size:13px;color:#ccc;margin-top:4px;line-height:1.5">'+p.description+'</p></div>'});h+='</div>'}
      if(d.optimized_internships&&d.optimized_internships.length>0){h+='<div style="margin:16px 0"><h4 style="color:var(--warning)">💼 优化实习经验</h4>';d.optimized_internships.forEach(function(intern){h+='<div style="margin:8px 0;padding:12px;background:rgba(255,171,0,0.05);border-left:3px solid var(--warning);border-radius:0 8px 8px 0"><b>'+intern.company+'</b> | '+intern.position+' <span style="color:var(--text-dim);font-size:12px">'+intern.duration+'</span><p style="font-size:13px;color:#ccc;margin-top:4px;line-height:1.5">'+intern.description+'</p></div>'});h+='</div>'}
      if(d.enhanced_skills&&d.enhanced_skills.length>0){h+='<div style="margin:16px 0"><h4 style="color:var(--accent)">🔧 增强技能列表</h4><div style="display:flex;flex-wrap:wrap;gap:8px">';d.enhanced_skills.forEach(function(s){h+='<span style="padding:4px 12px;background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.3);border-radius:20px;font-size:13px;color:var(--accent)">'+s+'</span>'});h+='</div></div>'}
      if(d.suggestions&&d.suggestions.length>0){h+='<div style="margin:16px 0"><h4 style="color:var(--text-dim)">💡 优化建议</h4>';d.suggestions.forEach(function(s){h+='<div style="font-size:13px;color:var(--accent2);margin:4px 0;padding:6px 10px;background:rgba(0,255,136,0.05);border-radius:6px">💡 '+s+'</div>'});h+='</div>'}
      h+='<div style="display:flex;gap:12px;margin-top:16px"><button class="btn btn-glow" onclick="exportResume()" style="flex:1">📥 导出简历</button><button class="btn" onclick="overwriteResume()" style="flex:1;border-color:var(--warning);color:var(--warning)">💾 覆盖原简历</button></div></div>';
      rd.innerHTML=h;
      window._lastOptimized=d;
    }else{rd.innerHTML='<div class="card"><p style="color:#ff4081">'+d.error+'</p></div>'}
  }catch(e){rd.innerHTML='<div class="card"><p style="color:#ff4081">'+e.message+'</p></div>'}
}


function exportResume(){
  var d=window._lastOptimized;if(!d||!d.resume_file){alert("没有可导出的优化结果");return}
  window.open("/api/resume/export/"+encodeURIComponent(d.resume_file),"_blank");
}
async function overwriteResume(){
  var d=window._lastOptimized;if(!d||!d.resume_file){alert("没有可覆盖的优化结果");return}
  if(!confirm("确定要用AI优化结果覆盖原简历吗？\n\n此操作将替换简历中的个人总结、项目经验、实习经验和技能列表。"))return;
  try{
    var fd=new FormData();
    fd.append("resume_file",d.resume_file);
    fd.append("optimized_summary",d.optimized_summary||"");
    fd.append("optimized_projects",JSON.stringify(d.optimized_projects||[]));
    fd.append("optimized_internships",JSON.stringify(d.optimized_internships||[]));
    fd.append("enhanced_skills",JSON.stringify(d.enhanced_skills||[]));
    fd.append("target",d.target||"");
    var r=await fetch("/api/resume/overwrite",{method:"POST",body:fd});
    var result=await r.json();
    if(result.ok){
      L(new Date().toLocaleTimeString(),"success","简历已覆盖更新！求职意向已同步");
      alert("简历已成功覆盖！\n\n求职意向已更新为目标岗位。\n即将跳转到岗位采集...");
      activeStepId=4;renderSteps();renderCenter();slideInCenter();
      sessionStorage.setItem("activeStep",4);
    }else{
      L(new Date().toLocaleTimeString(),"error","覆盖失败: "+result.error);
      alert("覆盖失败: "+result.error);
    }
  }catch(e){
    L(new Date().toLocaleTimeString(),"error","覆盖错误: "+e.message);
    alert("覆盖出错: "+e.message);
  }
}

async function loadTemplateResumes(){
  try{var r=await fetch("/api/resumes/list");var d=await r.json();var sel=document.getElementById("tresume");
  if(!sel)return;sel.innerHTML='<option value="">选择简历...</option>'+d.resumes.map(function(x){
    return '<option value="'+x.filename+'">'+x.name+(x.position?" - "+x.position:"")+'</option>'
  }).join("")}catch(e){}
}
async function uploadPhoto(){
  var rf=document.getElementById("tresume").value;
  if(!rf){alert("请先选择简历");return}
  var file=document.getElementById("tphoto").files[0];
  if(!file)return;
  var fd=new FormData();
  var sel=document.getElementById("tresume");
  var name=sel.options[sel.selectedIndex].text.split(" - ")[0];
  fd.append("resume_name",name);fd.append("photo",file);
  document.getElementById("tphotoStatus").textContent="上传中...";
  try{
    var r=await fetch("/api/resume/photo",{method:"POST",body:fd});
    var d=await r.json();
    if(d.ok){document.getElementById("tphotoStatus").textContent="已上传";L(new Date().toLocaleTimeString(),"success","照片已上传")}
    else{document.getElementById("tphotoStatus").textContent="失败"}
  }catch(e){document.getElementById("tphotoStatus").textContent="失败"}
}
function getTemplateStyle(){
  var rbs=document.getElementsByName("tstyle");
  for(var i=0;i<rbs.length;i++){if(rbs[i].checked)return rbs[i].value}
  return "classic";
}
async function previewTemplate(){
  var rf=document.getElementById("tresume").value;
  if(!rf){alert("请先选择简历");return}
  var style=getTemplateStyle();
  var preview=document.getElementById("tpreview");
  var _pb3=P(preview,'生成简历模板',5000);
  try{
    var fd=new FormData();fd.append("resume_file",rf);fd.append("template_style",style);
    var r=await fetch("/api/resume/template",{method:"POST",body:fd});
    var html=await r.text();
    preview.innerHTML='<iframe srcdoc="'+html.replace(/"/g,"&quot;")+'" style="width:100%;height:500px;border:none;background:#fff"></iframe>';
  }catch(e){preview.innerHTML='<p style="color:#ff4081;padding:20px">预览失败: '+e.message+'</p>'}
}
async function downloadTemplate(fmt){
  var rf=document.getElementById("tresume").value;
  if(!rf){alert("请先选择简历");return}
  var style=getTemplateStyle();
  var fd=new FormData();fd.append("resume_file",rf);fd.append("template_style",style);
  var r=await fetch("/api/resume/template",{method:"POST",body:fd});
  var html=await r.text();
  if(fmt==="pdf"){
    var w=window.open("","_blank");
    w.document.write(html);
    w.document.close();
    setTimeout(function(){w.print()},500);
  }else{
    var blob=new Blob([html],{type:"text/html;charset=utf-8"});
    var a=document.createElement("a");a.href=URL.createObjectURL(blob);
    a.download="resume_"+new Date().toISOString().slice(0,10)+".html";
    a.click();URL.revokeObjectURL(a.href);
  }
}


function renderPrecisionUI(){
  var h='<div class="card"><h3>🎯 精准简历优化</h3><p style="color:var(--text-dim);margin-bottom:12px">针对JD匹配>=70分的岗位，逐岗读取JD定向优化简历</p>';
  h+='<div style="margin-bottom:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">';
  h+='<select id="pJobsFile" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;font-size:13px"><option value="">选择采集记录...</option></select>';
  h+='<select id="pResume" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;font-size:13px"><option value="">选择简历</option></select>';
  h+='<span style="color:var(--text-dim);font-size:12px">阈值:</span><input id="pTh" type="number" value="70" min="0" max="100" style="background:#111;border:1px solid var(--border);color:#fff;padding:6px 10px;border-radius:6px;width:70px;font-size:13px">';
  h+='<button class="btn btn-primary" onclick="loadPrecisionJobs()" style="font-size:13px">🔍 加载岗位</button>';
  h+='</div><div id="pJobList" style="max-height:40vh;overflow-y:auto;margin-bottom:12px"><p style="color:var(--text-dim);text-align:center;padding:20px">选择采集结果和简历后点击「加载岗位」</p></div>';
  h+='<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn btn-glow" onclick="runPrecisionOptimize()">🚀 开始精准优化</button></div>';
  h+='<div id="pResult" style="margin-top:16px"></div></div>';
  loadPrecisionOpts2();
  return h;
}

async function loadPrecisionOpts2(){
  try{var r=await fetch("/api/jobs/list");var d=await r.json();var sel=document.getElementById("pJobsFile");
  if(sel&&d.files&&d.files.length>0){var _pjf=sel.value;sel.innerHTML='<option value="">选择采集记录...</option>'+d.files.map(function(f,i){var n=d.files.length-i;return '<option value="'+f.filename+'">第'+n+'次采集 · '+(f.keywords&&f.keywords[0]?f.keywords[0]:"未知")+' · '+f.count+'个岗位</option>'}).join("");if(_pjf&&d.files.some(function(f){return f.filename===_pjf})){sel.value=_pjf}else if(d.files[0]){sel.value=d.files[0].filename}}}catch(e){}
  try{var r2=await fetch("/api/resumes/list");var d2=await r2.json();var sel2=document.getElementById("pResume");
  if(sel2&&d2.resumes){var _prf=sel2.value;sel2.innerHTML='<option value="">选择简历...</option>'+d2.resumes.map(function(x){return '<option value="'+x.filename+'">'+x.name+(x.position?" - "+x.position:"")+'</option>'}).join("");if(_prf&&d2.resumes.some(function(x){return x.filename===_prf})){sel2.value=_prf}}}catch(e){}
}
var _precisionJobs=[];

async function loadPrecisionJobs(){
  var jf=document.getElementById("pJobsFile").value;
  var rf=document.getElementById("pResume").value;
  var th=parseInt(document.getElementById("pTh").value)||70;
  var el=document.getElementById("pJobList");
  if(!jf||!rf){alert("请先选择采集记录和简历\njf="+JSON.stringify(jf)+"\nrf="+JSON.stringify(rf));return}
  var _pb=P(el,'加载候选人列表',8000);
  try{
    var fd=new FormData();fd.append("jobs_file",jf);fd.append("resume_file",rf);fd.append("threshold",th);
    var r=await fetch("/api/deliver/list",{method:"POST",body:fd});var d=await r.json();
    if(d.ok&&d.jobs&&d.jobs.length>0){
      _precisionJobs=d.jobs;
      var h='<p style="color:var(--text-dim);font-size:12px;margin-bottom:12px">共 '+d.total_jobs+' 个岗位，符合阈值 >= '+th+' 分的有 '+d.candidates+' 个</p>';
      h+='<div style="margin-bottom:8px"><label style="cursor:pointer;color:var(--accent);font-size:12px"><input type="checkbox" id="pSelectAll" onchange="togglePSelectAll(this)"> 全选</label></div>';
      d.jobs.forEach(function(j,i){
        var sc=j.match_score||0;
        var scColor=sc>=75?"#0f0":sc>=50?"#ffab00":"#ff4081";
        h+='<div class="job-card" style="margin-bottom:6px;padding:10px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:8px;display:flex;align-items:center;gap:10px">';
        h+='<input type="checkbox" class="pJobCb" value="'+i+'" style="accent-color:var(--accent)">';
        h+='<div style="min-width:36px;height:36px;border-radius:50%;background:radial-gradient(circle,'+scColor+'33,transparent 70%);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:'+scColor+'">'+sc+'</div>';
        h+='<div style="flex:1;min-width:0"><div style="font-size:13px;font-weight:600;color:#fff">'+j.title+'</div><div style="font-size:11px;color:var(--text-dim)">'+j.company+' · '+j.salary+' · '+j.location+'</div></div>';
        h+='</div>'
      });
      el.innerHTML=h
    }else{el.innerHTML='<div style="text-align:center;padding:40px;color:var(--text-dim)">没有 >= '+th+' 分的岗位（请先运行步骤5 JD匹配）</div>'}
  }catch(e){el.innerHTML='<div style="text-align:center;padding:40px;color:#ff4081">加载失败: '+e.message+'</div>'}
}

function togglePSelectAll(cb){var cbs=document.querySelectorAll(".pJobCb");cbs.forEach(function(c){c.checked=cb.checked})}

async function runPrecisionOptimize(){
  var jf=document.getElementById("pJobsFile").value;
  var rf=document.getElementById("pResume").value;
  if(!jf||!rf){alert("请先选择采集记录和简历\njf="+JSON.stringify(jf)+"\nrf="+JSON.stringify(rf));return}
  var cbs=document.querySelectorAll(".pJobCb:checked");
  if(cbs.length===0){alert("请至少勾选一个岗位\n已加载岗位数: "+_precisionJobs.length);return}
  var indices=[];cbs.forEach(function(c){indices.push(c.value)});
  var el=document.getElementById("pResult");
  var _pb6=P(el,'DeepSeek三维评分 · 抓取'+indices.length+'个JD',indices.length*8000);
  try{
    var fd=new FormData();fd.append("resume_file",rf);fd.append("jobs_file",jf);fd.append("job_indices",indices.join(","));
    var r=await fetch("/api/resume/precision-optimize",{method:"POST",body:fd});var d=await r.json();
    if(d.ok){
      window._lastPrecision=d;
      var h='<div class="card" style="border-color:var(--accent)"><h3 style="color:#0f0;margin-bottom:12px">✅ 精准优化完成</h3>';
      if(d.target_position)h+='<p><b>目标:</b> '+d.target_position+'</p>';
      if(d.optimized_summary)h+='<p style="margin-top:8px"><b>优化评价:</b><br><span style="color:var(--text-dim)">'+d.optimized_summary+'</span></p>';
      if(d.enhanced_skills&&d.enhanced_skills.length)h+='<p style="margin-top:8px"><b>技能:</b> '+d.enhanced_skills.join(", ")+'</p>';
      if(d.optimized_projects&&d.optimized_projects.length){h+='<p style="margin-top:8px"><b>项目:</b></p>';d.optimized_projects.forEach(function(pj){h+='<div style="margin-left:12px;margin-bottom:6px;padding:8px;background:rgba(255,255,255,0.03);border-radius:6px"><b>'+pj.name+'</b> <span style="color:var(--text-dim)">('+pj.role+')</span><br><span style="color:var(--text-dim);font-size:12px">'+pj.description+'</span></div>'})}
      if(d.optimization_notes)h+='<p style="margin-top:8px;color:var(--accent2);font-size:12px">📝 '+d.optimization_notes+'</p>';
      h+='<div style="margin-top:12px;display:flex;gap:8px"><button class="btn btn-glow" onclick="overwritePrecisionResume()">📝 覆盖简历</button><button class="btn btn-primary" onclick="copyPrecisionResult()">📋 复制</button></div></div>';
      el.innerHTML=h;L(new Date().toLocaleTimeString(),"success","精准优化完成")
    }else{el.innerHTML='<div class="card"><p style="color:#ff4081">'+d.error+'</p></div>'}
  }catch(e){el.innerHTML='<div class="card"><p style="color:#ff4081">'+e.message+'</p></div>'}
}

async function overwritePrecisionResume(){
  var d=window._lastPrecision;if(!d||!d.resume_file){alert("无结果");return}
  if(!confirm("确定覆盖简历？"))return;
  try{
    var fd=new FormData();fd.append("resume_file",d.resume_file);
    fd.append("optimized_summary",d.optimized_summary||"");
    fd.append("optimized_projects",JSON.stringify(d.optimized_projects||[]));
    fd.append("optimized_internships","[]");
    fd.append("enhanced_skills",JSON.stringify(d.enhanced_skills||[]));
    fd.append("target",d.target_position||"");
    var r=await fetch("/api/resume/overwrite",{method:"POST",body:fd});var result=await r.json();
    if(result.ok){L(new Date().toLocaleTimeString(),"success","已覆盖");alert("简历已精准覆盖！")}
    else{alert("失败: "+result.error)}
  }catch(e){alert("出错: "+e.message)}
}

function copyPrecisionResult(){
  var d=window._lastPrecision;if(!d){alert("无结果");return}
  var t="精准简历优化\n\n";if(d.target_position)t+="目标: "+d.target_position+"\n";
  if(d.optimized_summary)t+="评价: "+d.optimized_summary+"\n";
  if(d.enhanced_skills)t+="技能: "+d.enhanced_skills.join(", ")+"\n";
  if(d.optimized_projects)d.optimized_projects.forEach(function(pj){t+=pj.name+" - "+pj.description+"\n"});
  navigator.clipboard.writeText(t).then(function(){L(new Date().toLocaleTimeString(),"success","已复制")}).catch(function(){alert("复制失败")})
}

async function syncServer(){try{var r=await fetch("/api/status");var d=await r.json();if(d.steps){stepsData=d.steps;renderSteps()}if(d.stats){statsData=d.stats;R()}S("已连接","#0f0")}catch(e){}}

// Init
activeStepId=parseInt(sessionStorage.getItem("activeStep"))||0;var welcomeHTML=document.getElementById("centerBody").innerHTML;
renderSteps();R();renderCenter();
S("就绪","#0f0");L("--:--:--","success","v7 启动");
syncServer();setInterval(syncServer,30000);
async function loadDeliverOpts(){
  try{
    var r=await fetch("/api/jobs/list");
    var d=await r.json();
    var sel=document.getElementById("dJobsFile");
    if(sel&&d.files&&d.files.length>0){
      sel.innerHTML='<option value="">??????</option>'+d.files.map(function(f){return '<option value="'+f.filename+'">'+f.collected_at.slice(0,16)+' ('+f.count+'?)</option>'}).join("");
      if(d.files[0])sel.value=d.files[0].filename
    }
  }catch(e){}
  try{
    var r2=await fetch("/api/resumes/list");
    var d2=await r2.json();
    var sel2=document.getElementById("dResume");
    if(sel2&&d2.resumes){
      sel2.innerHTML='<option value="">????</option>'+d2.resumes.map(function(x){return '<option value="'+x.filename+'">'+x.name+'</option>'}).join("")
    }
  }catch(e){}
}

async function uploadResume(){var f=document.getElementById("rf").files[0];if(!f)return;var fd=new FormData();fd.append("file",f);L(new Date().toLocaleTimeString(),"info","解析中: "+f.name);try{var r=await fetch("/api/resumes/upload",{method:"POST",body:fd});var d=await r.json();if(d.ok){L(new Date().toLocaleTimeString(),"success","解析成功");loadResumeList()}else{L(new Date().toLocaleTimeString(),"error",d.error||"失败")}}catch(e){L(new Date().toLocaleTimeString(),"error","上传失败")}}





async function loadOptResumes(){
  try{var r=await fetch("/api/resumes/list");var d=await r.json();var sel=document.getElementById("oresume");
  if(!sel)return;sel.innerHTML='<option value="">选择简历...</option>'+d.resumes.map(function(x){
    return '<option value="'+x.filename+'">'+x.name+(x.position?" - "+x.position:"")+'</option>'
  }).join("")}catch(e){}
}
async function optimizeResume(){
  var rf=document.getElementById("oresume").value;
  var target=document.getElementById("otarget").value.trim();
  var extra=document.getElementById("oextra").value.trim();
  if(!rf){alert("请选择一份已解析的简历");return}
  if(!target){alert("请填写求职意向");return}
  var rd=document.getElementById("oresult");
  var _pb5=P(rd,'DeepSeek三维评分',18000);
  try{
    var fd=new FormData();fd.append("resume_file",rf);fd.append("target",target);fd.append("extra",extra);
    var r=await fetch("/api/resume/optimize",{method:"POST",body:fd});
    var d=await r.json();
    if(d.ok){
      var h='<div class="card"><h3>✨ 三维度优化结果</h3>';
      h+='<div style="margin:12px 0;padding:10px;background:rgba(0,229,255,0.05);border-left:3px solid var(--accent);border-radius:0 8px 8px 0"><b style="color:var(--accent)">求职意向: </b>'+d.target+'</div>';if(d.job_analysis)h+='<div style="margin:8px 0;padding:10px;background:rgba(255,171,0,0.05);border-left:3px solid var(--warning);border-radius:0 8px 8px 0;font-size:13px;color:var(--accent2);line-height:1.5">🔍 <b>岗位分析:</b> '+d.job_analysis+'</div>';
      if(d.optimized_summary)h+='<div style="margin:16px 0"><h4 style="color:var(--accent)">📝 优化后个人总结</h4><p style="color:#fff;white-space:pre-wrap;line-height:1.6">'+d.optimized_summary+'</p></div>';
      if(d.optimized_projects&&d.optimized_projects.length>0){h+='<div style="margin:16px 0"><h4 style="color:var(--accent2)">🚀 优化项目经验</h4>';d.optimized_projects.forEach(function(p){h+='<div style="margin:8px 0;padding:12px;background:rgba(0,255,136,0.05);border-left:3px solid var(--accent2);border-radius:0 8px 8px 0"><b>'+p.name+'</b> — <span style="color:var(--text-dim);font-size:13px">'+p.role+'</span><p style="font-size:13px;color:#ccc;margin-top:4px;line-height:1.5">'+p.description+'</p></div>'});h+='</div>'}
      if(d.optimized_internships&&d.optimized_internships.length>0){h+='<div style="margin:16px 0"><h4 style="color:var(--warning)">💼 优化实习经验</h4>';d.optimized_internships.forEach(function(intern){h+='<div style="margin:8px 0;padding:12px;background:rgba(255,171,0,0.05);border-left:3px solid var(--warning);border-radius:0 8px 8px 0"><b>'+intern.company+'</b> | '+intern.position+' <span style="color:var(--text-dim);font-size:12px">'+intern.duration+'</span><p style="font-size:13px;color:#ccc;margin-top:4px;line-height:1.5">'+intern.description+'</p></div>'});h+='</div>'}
      if(d.enhanced_skills&&d.enhanced_skills.length>0){h+='<div style="margin:16px 0"><h4 style="color:var(--accent)">🔧 增强技能列表</h4><div style="display:flex;flex-wrap:wrap;gap:8px">';d.enhanced_skills.forEach(function(s){h+='<span style="padding:4px 12px;background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.3);border-radius:20px;font-size:13px;color:var(--accent)">'+s+'</span>'});h+='</div></div>'}
      if(d.suggestions&&d.suggestions.length>0){h+='<div style="margin:16px 0"><h4 style="color:var(--text-dim)">💡 优化建议</h4>';d.suggestions.forEach(function(s){h+='<div style="font-size:13px;color:var(--accent2);margin:4px 0;padding:6px 10px;background:rgba(0,255,136,0.05);border-radius:6px">💡 '+s+'</div>'});h+='</div>'}
      h+='<div style="display:flex;gap:12px;margin-top:16px"><button class="btn btn-glow" onclick="exportResume()" style="flex:1">📥 导出简历</button><button class="btn" onclick="overwriteResume()" style="flex:1;border-color:var(--warning);color:var(--warning)">💾 覆盖原简历</button></div></div>';
      rd.innerHTML=h;
      window._lastOptimized=d;
    }else{rd.innerHTML='<div class="card"><p style="color:#ff4081">'+d.error+'</p></div>'}
  }catch(e){rd.innerHTML='<div class="card"><p style="color:#ff4081">'+e.message+'</p></div>'}
}

async function overwriteResume(){
  var d=window._lastOptimized;if(!d||!d.resume_file){alert("没有可覆盖的优化结果");return}
  if(!confirm("确定要用AI优化结果覆盖原简历吗？\n\n此操作将替换简历中的个人总结、项目经验、实习经验和技能列表。"))return;
  try{
    var fd=new FormData();
    fd.append("resume_file",d.resume_file);
    fd.append("optimized_summary",d.optimized_summary||"");
    fd.append("optimized_projects",JSON.stringify(d.optimized_projects||[]));
    fd.append("optimized_internships",JSON.stringify(d.optimized_internships||[]));
    fd.append("enhanced_skills",JSON.stringify(d.enhanced_skills||[]));
    fd.append("target",d.target||"");
    var r=await fetch("/api/resume/overwrite",{method:"POST",body:fd});
    var result=await r.json();
    if(result.ok){
      L(new Date().toLocaleTimeString(),"success","简历已覆盖更新！求职意向已同步");
      alert("简历已成功覆盖！\n\n求职意向已更新为目标岗位。\n即将跳转到岗位采集...");
      activeStepId=4;renderSteps();renderCenter();slideInCenter();
      sessionStorage.setItem("activeStep",4);
    }else{
      L(new Date().toLocaleTimeString(),"error","覆盖失败: "+result.error);
      alert("覆盖失败: "+result.error);
    }
  }catch(e){
    L(new Date().toLocaleTimeString(),"error","覆盖错误: "+e.message);
    alert("覆盖出错: "+e.message);
  }
}
