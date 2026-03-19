let currentVehicle = null;
let recentBills = [];

document.addEventListener('DOMContentLoaded', function() {
    updateBillTotal();
    loadRecentBills();
    
    document.querySelectorAll('input[name="fuel_type"]').forEach(radio => {
        radio.addEventListener('change', updateBillTotal);
    });
});

async function checkVehicle() {
    const plateNumber = document.getElementById('billing-plate').value.trim();
    
    if (!plateNumber) {
        showNotification('Please enter a plate number', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/wallet/${encodeURIComponent(plateNumber)}`);
        const result = await response.json();
        
        if (result.success && result.wallet) {
            currentVehicle = result.wallet;
            document.getElementById('info-owner').textContent = result.wallet.owner;
            document.getElementById('info-vehicle-type').textContent = result.wallet.vehicle_type;
            document.getElementById('info-balance').textContent = '\u20B9' + parseFloat(result.wallet.balance).toFixed(2);
            document.getElementById('vehicle-info').style.display = 'block';
            showNotification('Vehicle verified successfully', 'success');
        } else {
            currentVehicle = null;
            document.getElementById('vehicle-info').style.display = 'none';
            showNotification('Vehicle not registered. Please register first.', 'error');
        }
    } catch (error) {
        showNotification('Error checking vehicle: ' + error.message, 'error');
    }
}

function adjustQuantity(delta) {
    const input = document.getElementById('billing-quantity');
    let value = parseFloat(input.value) || 0;
    value = Math.max(0.5, value + delta);
    input.value = value.toFixed(1);
    updateBillTotal();
}

function setQuantity(qty) {
    document.getElementById('billing-quantity').value = qty;
    updateBillTotal();
}

function updateBillTotal() {
    const fuelRadio = document.querySelector('input[name="fuel_type"]:checked');
    const quantity = parseFloat(document.getElementById('billing-quantity').value) || 0;
    
    if (fuelRadio) {
        const fuelType = fuelRadio.value;
        const price = parseFloat(fuelRadio.dataset.price);
        const total = quantity * price;
        
        document.getElementById('summary-fuel').textContent = fuelType;
        document.getElementById('summary-qty').textContent = quantity.toFixed(2) + ' L';
        document.getElementById('summary-rate').textContent = '\u20B9' + price.toFixed(2) + '/L';
        document.getElementById('summary-total').textContent = '\u20B9' + total.toFixed(2);
    }
}

async function processBilling(event) {
    event.preventDefault();
    
    const plateNumber = document.getElementById('billing-plate').value.trim();
    const fuelRadio = document.querySelector('input[name="fuel_type"]:checked');
    const quantity = parseFloat(document.getElementById('billing-quantity').value) || 0;
    
    if (!plateNumber) {
        showNotification('Please enter a plate number', 'error');
        return false;
    }
    
    if (!fuelRadio) {
        showNotification('Please select a fuel type', 'error');
        return false;
    }
    
    if (quantity <= 0) {
        showNotification('Please enter a valid quantity', 'error');
        return false;
    }
    
    const fuelType = fuelRadio.value;
    
    try {
        const response = await fetch('/api/fuel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                plate_number: plateNumber,
                fuel_type: fuelType,
                liters: quantity
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showReceipt(result, plateNumber);
            addToRecentBills(result, plateNumber);
            
            if (currentVehicle) {
                document.getElementById('info-balance').textContent = '\u20B9' + result.new_balance.toFixed(2);
            }
        } else {
            showNotification(result.message || result.error || 'Billing failed', 'error');
        }
    } catch (error) {
        showNotification('Error processing bill: ' + error.message, 'error');
    }
    
    return false;
}

function showReceipt(result, plateNumber) {
    const modal = document.getElementById('bill-receipt-modal');
    const content = document.getElementById('receipt-content');
    const timeEl = document.getElementById('receipt-time');
    
    const now = new Date();
    timeEl.textContent = now.toLocaleString();
    
    content.innerHTML = `
        <div class="receipt-row">
            <span>Bill No:</span>
            <span>#${result.transaction_id}</span>
        </div>
        <div class="receipt-row">
            <span>Vehicle:</span>
            <span>${plateNumber}</span>
        </div>
        <div class="receipt-row">
            <span>Customer:</span>
            <span>${result.owner}</span>
        </div>
        <div class="receipt-divider-small"></div>
        <div class="receipt-row">
            <span>Fuel Type:</span>
            <span>${result.fuel_type}</span>
        </div>
        <div class="receipt-row">
            <span>Quantity:</span>
            <span>${result.liters.toFixed(2)} L</span>
        </div>
        <div class="receipt-row">
            <span>Rate:</span>
            <span>\u20B9${result.price_per_liter.toFixed(2)}/L</span>
        </div>
        <div class="receipt-divider-small"></div>
        <div class="receipt-row total">
            <span>Total:</span>
            <span>\u20B9${result.total_amount.toFixed(2)}</span>
        </div>
        <div class="receipt-row">
            <span>New Balance:</span>
            <span>\u20B9${result.new_balance.toFixed(2)}</span>
        </div>
    `;
    
    modal.style.display = 'flex';
}

function closeReceipt() {
    document.getElementById('bill-receipt-modal').style.display = 'none';
    document.getElementById('billing-plate').value = '';
    document.getElementById('billing-quantity').value = '5';
    document.getElementById('vehicle-info').style.display = 'none';
    currentVehicle = null;
    updateBillTotal();
}

function printReceipt() {
    window.print();
}

function addToRecentBills(result, plateNumber) {
    const bill = {
        id: result.transaction_id,
        plate: plateNumber,
        owner: result.owner,
        fuel_type: result.fuel_type,
        liters: result.liters,
        amount: result.total_amount,
        time: new Date().toLocaleTimeString()
    };
    
    recentBills.unshift(bill);
    if (recentBills.length > 10) recentBills.pop();
    
    renderRecentBills();
}

function loadRecentBills() {
    renderRecentBills();
}

function renderRecentBills() {
    const container = document.getElementById('recent-bills');
    
    if (recentBills.length === 0) {
        container.innerHTML = '<p class="no-bills">No bills generated yet today</p>';
        return;
    }
    
    let html = '<div class="bills-list">';
    recentBills.forEach(bill => {
        html += `
            <div class="bill-item">
                <div class="bill-header">
                    <span class="bill-id">#${bill.id}</span>
                    <span class="bill-time">${bill.time}</span>
                </div>
                <div class="bill-details">
                    <span class="bill-plate">${bill.plate}</span>
                    <span class="bill-fuel">${bill.fuel_type} - ${bill.liters}L</span>
                    <span class="bill-amount">\u20B9${bill.amount.toFixed(2)}</span>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
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
    
    setTimeout(() => notification.remove(), 3000);
}
