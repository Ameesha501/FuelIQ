// static/js/dashboard.js
const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext ? canvas.getContext('2d') : null;
const preview = document.getElementById('preview');
const plateTextEl = document.getElementById('plateText');
const walletInfoEl = document.getElementById('walletInfo');
const billingBlock = document.getElementById('billingBlock');
const billDetails = document.getElementById('billDetails');
const billAmountEl = document.getElementById('billAmount');

function log(msg){
  const el = document.getElementById('logs');
  const p = document.createElement('div');
  p.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  el.prepend(p);
}

async function postJson(url, data){
  const res = await fetch(url, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(data)
  });
  return res.json();
}

// start webcam
if(navigator.mediaDevices && navigator.mediaDevices.getUserMedia){
  navigator.mediaDevices.getUserMedia({video:true}).then(stream=>{
    video.srcObject = stream;
  }).catch(e=>{
    log('Webcam error: ' + e.message);
  });
}

// capture
document.getElementById('snapBtn').addEventListener('click', async ()=>{
  if(!ctx) return;
  canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  ctx.drawImage(video, 0, 0);
  const dataUrl = canvas.toDataURL('image/jpeg');
  preview.src = dataUrl;
  await detectImage(dataUrl);
});

// upload file
document.getElementById('imgInput').addEventListener('change', async (e)=>{
  const file = e.target.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = async ()=>{
    preview.src = reader.result;
    await detectImage(reader.result);
  };
  reader.readAsDataURL(file);
});

async function detectImage(dataUrl){
  log('Sending image for detection...');
  const r = await postJson('/detect', {image: dataUrl});
  if(r.error){ log('Detect error: '+ r.error); return; }
  plateTextEl.textContent = r.plate_text || '-';
  if(r.wallet){
    walletInfoEl.textContent = `ID: ${r.wallet.wallet_id} | Balance: ${r.wallet.balance}`;
    billingBlock.style.display = 'block';
  } else {
    walletInfoEl.textContent = 'No wallet found';
    billingBlock.style.display = 'block'; // show so user can recharge/create
  }
}

// generate bill
document.getElementById('generateBill').addEventListener('click', ()=>{
  const liters = parseFloat(document.getElementById('liters').value || 0);
  const rate = parseFloat(document.getElementById('rate').value || 0);
  const total = parseFloat((liters*rate).toFixed(2));
  billAmountEl.textContent = total;
  billDetails.style.display = 'block';
  log(`Bill generated ₹${total}`);
});

// purchase (auto-debit)
document.getElementById('purchaseBtn').addEventListener('click', async ()=>{
  const plate = (plateTextEl.textContent || "").trim();
  const liters = parseFloat(document.getElementById('liters').value || 0);
  const rate = parseFloat(document.getElementById('rate').value || 0);
  const fuel_type = document.getElementById('fuelType').value;
  const r = await postJson('/purchase', {plate, liters, rate, fuel_type});
  if(r.error){ log('Purchase error: '+ r.error); return; }
  if(r.status === 'success'){
    log(`Purchase success ₹${r.amount}. New balance: ${r.new_balance}`);
    walletInfoEl.textContent = `Balance: ${r.new_balance}`;
  } else if(r.status === 'insufficient_balance'){
    log(`Insufficient balance. Need ₹${r.required}, have ₹${r.balance}`);
  }
});

// download invoice -> opens new tab with invoice page (POST)
document.getElementById('downloadBill').addEventListener('click', async ()=>{
  const plate = (plateTextEl.textContent || "").trim();
  const liters = parseFloat(document.getElementById('liters').value || 0);
  const rate = parseFloat(document.getElementById('rate').value || 0);
  const fuel_type = document.getElementById('fuelType').value;
  const total = parseFloat((liters*rate).toFixed(2));

  // create a form to POST to /invoice and open in new tab
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = '/invoice';
  form.target = '_blank';
  const payload = {plate, liters, rate, fuel_type, total, date: new Date().toLocaleString()};
  const input = document.createElement('input');
  input.type = 'hidden';
  input.name = 'data';
  input.value = JSON.stringify(payload);
  form.appendChild(input);
  document.body.appendChild(form);

  // We will call server via fetch to render template and open new window with returned HTML:
  const res = await fetch('/invoice', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const html = await res.text();
  const win = window.open("", "_blank");
  win.document.open();
  win.document.write(html);
  win.document.close();
  log('Invoice opened in new tab.');
});

// wallet upload form
document.getElementById('walletForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch('/wallet_upload', {method:'POST', body: fd});
  const json = await res.json();
  log('Wallet upload: ' + JSON.stringify(json));
});
