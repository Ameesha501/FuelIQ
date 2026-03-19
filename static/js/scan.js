let stream = null;
let detectedPlate = null;

function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(tabName + '-tab').classList.add('active');
    event.target.classList.add('active');
    
    if (tabName !== 'camera' && stream) {
        stopCamera();
    }
}

const dropZone = document.getElementById('dropZone');
const imageInput = document.getElementById('imageInput');

if (dropZone) {
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
            handleImageSelect(file);
        }
    });
}

if (imageInput) {
    imageInput.addEventListener('change', (e) => {
        if (e.target.files[0]) {
            handleImageSelect(e.target.files[0]);
        }
    });
}

function handleImageSelect(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('imagePreview').src = e.target.result;
        document.getElementById('preview-container').style.display = 'block';
        document.getElementById('dropZone').style.display = 'none';
    };
    reader.readAsDataURL(file);
}

async function startCamera() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ 
            video: { facingMode: 'environment', width: 1280, height: 720 } 
        });
        const video = document.getElementById('video');
        video.srcObject = stream;
        
        document.getElementById('startCamera').style.display = 'none';
        document.getElementById('captureBtn').style.display = 'inline-block';
        document.getElementById('stopCamera').style.display = 'inline-block';
    } catch (error) {
        alert('Could not access camera: ' + error.message);
    }
}

function stopCamera() {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    document.getElementById('video').srcObject = null;
    document.getElementById('startCamera').style.display = 'inline-block';
    document.getElementById('captureBtn').style.display = 'none';
    document.getElementById('stopCamera').style.display = 'none';
}

function captureImage() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    
    const imageData = canvas.toDataURL('image/jpeg');
    sendImageForDetection(imageData);
}

async function detectPlate() {
    const imageFile = document.getElementById('imageInput').files[0];
    if (!imageFile) {
        alert('Please select an image first');
        return;
    }
    
    const formData = new FormData();
    formData.append('image', imageFile);
    
    try {
        const response = await fetch('/api/detect', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        handleDetectionResult(result);
    } catch (error) {
        showNotification('Error detecting plate: ' + error.message, 'error');
    }
}

async function sendImageForDetection(imageData) {
    const formData = new FormData();
    formData.append('image_data', imageData);
    
    try {
        const response = await fetch('/api/detect', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        handleDetectionResult(result);
    } catch (error) {
        showNotification('Error detecting plate: ' + error.message, 'error');
    }
}

function handleDetectionResult(result) {
    const resultContainer = document.getElementById('detection-result');
    const resultContent = document.getElementById('result-content');
    
    if (result.success) {
        detectedPlate = result.plate_number;
        
        let html = `<div class="detected-plate">${result.plate_number}</div>`;
        
        if (result.registered && result.wallet) {
            html += `
                <div class="wallet-info">
                    <div class="wallet-info-item">
                        <div class="wallet-info-label">Owner</div>
                        <div class="wallet-info-value">${result.wallet.owner}</div>
                    </div>
                    <div class="wallet-info-item">
                        <div class="wallet-info-label">Vehicle Type</div>
                        <div class="wallet-info-value">${result.wallet.vehicle_type}</div>
                    </div>
                    <div class="wallet-info-item">
                        <div class="wallet-info-label">Balance</div>
                        <div class="wallet-info-value">\u20B9${parseFloat(result.wallet.balance).toFixed(2)}</div>
                    </div>
                </div>
            `;
            
            showFuelForm(result.plate_number, result.wallet);
        } else {
            html += `<p style="color: #ea580c; margin-top: 1rem;">Vehicle not registered in the system.</p>`;
            showRegisterForm(result.plate_number);
        }
        
        resultContent.innerHTML = html;
        resultContainer.style.display = 'block';
    } else {
        resultContent.innerHTML = `<p style="color: #dc2626;">${result.error || 'Could not detect plate number'}</p>`;
        resultContainer.style.display = 'block';
        document.getElementById('fuel-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'none';
    }
}

function showFuelForm(plateNumber, wallet) {
    document.getElementById('detected-plate').value = plateNumber;
    document.getElementById('owner-name').value = wallet.owner;
    document.getElementById('available-balance').value = '\u20B9' + parseFloat(wallet.balance).toFixed(2);
    document.getElementById('fuel-form').style.display = 'block';
    document.getElementById('register-form').style.display = 'none';
    calculateTotal();
}

function showRegisterForm(plateNumber) {
    document.getElementById('new-plate').value = plateNumber;
    document.getElementById('register-form').style.display = 'block';
    document.getElementById('fuel-form').style.display = 'none';
}

function calculateTotal() {
    const fuelType = document.getElementById('fuel-type');
    const quantity = parseFloat(document.getElementById('fuel-quantity').value) || 0;
    const pricePerLiter = parseFloat(fuelType.options[fuelType.selectedIndex].dataset.price);
    const total = quantity * pricePerLiter;
    document.getElementById('total-amount').value = '\u20B9' + total.toFixed(2);
}

document.getElementById('fuel-type')?.addEventListener('change', calculateTotal);

async function processFueling() {
    const plateNumber = document.getElementById('detected-plate').value;
    const fuelType = document.getElementById('fuel-type').value;
    const liters = parseFloat(document.getElementById('fuel-quantity').value);
    
    if (!plateNumber || liters <= 0) {
        showNotification('Please enter valid fuel quantity', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/fuel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                plate_number: plateNumber,
                fuel_type: fuelType,
                liters: liters
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccessModal(result);
        } else {
            showNotification(result.message || 'Fueling failed', 'error');
        }
    } catch (error) {
        showNotification('Error processing fueling: ' + error.message, 'error');
    }
}

function showSuccessModal(result) {
    const modal = document.getElementById('success-modal');
    const details = document.getElementById('success-details');
    
    details.innerHTML = `
        <table style="width: 100%; text-align: left; margin: 1rem 0;">
            <tr><td>Vehicle:</td><td><strong>${result.owner}</strong></td></tr>
            <tr><td>Fuel Type:</td><td>${result.fuel_type}</td></tr>
            <tr><td>Quantity:</td><td>${result.liters.toFixed(2)} Liters</td></tr>
            <tr><td>Amount:</td><td><strong>\u20B9${result.total_amount.toFixed(2)}</strong></td></tr>
            <tr><td>New Balance:</td><td>\u20B9${result.new_balance.toFixed(2)}</td></tr>
            <tr><td>Transaction ID:</td><td>#${result.transaction_id}</td></tr>
        </table>
    `;
    
    modal.style.display = 'flex';
}

function closeModal() {
    document.getElementById('success-modal').style.display = 'none';
    resetScanPage();
}

function resetScanPage() {
    document.getElementById('detection-result').style.display = 'none';
    document.getElementById('fuel-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'none';
    document.getElementById('preview-container').style.display = 'none';
    document.getElementById('dropZone').style.display = 'block';
    document.getElementById('imageInput').value = '';
    detectedPlate = null;
}

async function registerVehicle() {
    const plateNumber = document.getElementById('new-plate').value;
    const owner = document.getElementById('new-owner').value;
    const vehicleType = document.getElementById('new-vehicle-type').value;
    const initialBalance = parseFloat(document.getElementById('new-balance').value) || 0;
    
    if (!owner.trim()) {
        showNotification('Please enter owner name', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/wallet/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                plate_number: plateNumber,
                owner: owner,
                vehicle_type: vehicleType,
                initial_balance: initialBalance
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Vehicle registered successfully!', 'success');
            document.getElementById('register-form').style.display = 'none';
            
            if (result.wallet) {
                showFuelForm(plateNumber, result.wallet);
            }
        } else {
            showNotification(result.message || 'Registration failed', 'error');
        }
    } catch (error) {
        showNotification('Error registering vehicle: ' + error.message, 'error');
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'success' ? '#16a34a' : type === 'error' ? '#dc2626' : '#2563eb'};
        color: white;
        border-radius: 8px;
        z-index: 9999;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}
