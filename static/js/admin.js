function showAddWalletForm() {
    document.getElementById('add-wallet-form').style.display = 'block';
}

function hideAddWalletForm() {
    document.getElementById('add-wallet-form').style.display = 'none';
    document.getElementById('add-plate').value = '';
    document.getElementById('add-owner').value = '';
    document.getElementById('add-balance').value = '0';
}

async function createWallet(event) {
    event.preventDefault();
    
    const plateNumber = document.getElementById('add-plate').value.trim();
    const owner = document.getElementById('add-owner').value.trim();
    const vehicleType = document.getElementById('add-vehicle-type').value;
    const initialBalance = parseFloat(document.getElementById('add-balance').value) || 0;
    
    if (!plateNumber || !owner) {
        showNotification('Please fill in all required fields', 'error');
        return false;
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
            showNotification('Wallet created successfully!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(result.message || 'Failed to create wallet', 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
    
    return false;
}

function searchWallets() {
    const searchText = document.getElementById('searchInput').value.toLowerCase();
    const rows = document.querySelectorAll('#walletsTable tbody tr');
    
    rows.forEach(row => {
        const plate = row.querySelector('.plate-cell').textContent.toLowerCase();
        const owner = row.cells[1].textContent.toLowerCase();
        
        if (plate.includes(searchText) || owner.includes(searchText)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function showRechargeModal(plate, owner) {
    document.getElementById('recharge-plate').value = plate;
    document.getElementById('recharge-owner').value = owner;
    document.getElementById('recharge-amount').value = 500;
    document.getElementById('recharge-modal').style.display = 'flex';
}

function closeRechargeModal() {
    document.getElementById('recharge-modal').style.display = 'none';
}

function setRechargeAmount(amount) {
    document.getElementById('recharge-amount').value = amount;
}

async function processRecharge() {
    const plateNumber = document.getElementById('recharge-plate').value;
    const amount = parseFloat(document.getElementById('recharge-amount').value);
    
    if (amount <= 0) {
        showNotification('Please enter a valid amount', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/wallet/recharge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                plate_number: plateNumber,
                amount: amount
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification(`Added \u20B9${amount} to ${plateNumber}`, 'success');
            closeRechargeModal();
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(result.message || 'Recharge failed', 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

function viewTransactions(plate) {
    window.location.href = `/transactions?plate=${plate}`;
}

function confirmDelete(plate) {
    document.getElementById('delete-plate').value = plate;
    document.getElementById('delete-plate-display').textContent = plate;
    document.getElementById('delete-modal').style.display = 'flex';
}

function closeDeleteModal() {
    document.getElementById('delete-modal').style.display = 'none';
}

async function deleteWallet() {
    const plateNumber = document.getElementById('delete-plate').value;
    
    try {
        const response = await fetch('/api/wallet/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plate_number: plateNumber })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Wallet deleted successfully', 'success');
            closeDeleteModal();
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(result.message || 'Delete failed', 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
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

document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.style.display = 'none';
    }
});
