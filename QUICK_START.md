# FuelIQ - Quick Start Guide

## 🚀 Getting Started in 3 Steps

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run the Application
```bash
python app.py
```

### Step 3: Access the Application
Open your browser and go to: **http://localhost:5000**

## 🔐 Login Credentials

### Admin Login
- **Username**: `admin`
- **Password**: `admin123`

**OR**

- **Username**: `staff`
- **Password**: `staff123`

### User Login
- **Wallet ID**: Use any Wallet ID from your database (e.g., `W1`, `W2`)
- **Password**: Optional (not required for demo)

## 📋 Key Features to Test

### Admin Features

1. **Live Detection**
   - Navigate to "Live Detection"
   - Click "Start Camera"
   - Capture vehicle image
   - System detects number plate and verifies wallet

2. **Bill Generation** (Key Feature)
   - Go to "Bill Generation"
   - Vehicle details auto-filled
   - **Enter ONLY fuel quantity** (e.g., 10 liters)
   - All other fields auto-calculated
   - Submit to generate bill

3. **View Transactions**
   - See all fuel transactions
   - Filter and search

4. **Manage Wallets**
   - View all wallets
   - Check balances

### User Features

1. **View Dashboard**
   - See wallet balance
   - Recent transactions
   - Recent bills

2. **Recharge Wallet**
   - Enter amount
   - Quick amount buttons available
   - Confirm recharge

3. **View Bills**
   - See all fuel bills
   - View detailed bill
   - Print/Save as PDF

## 🎯 Demo Workflow

### Complete Fueling Process

1. **Admin**: Login as admin
2. **Admin**: Go to "Live Detection" or "Upload & Verify"
3. **Admin**: Detect vehicle number plate
4. **Admin**: Go to "Bill Generation"
5. **Admin**: Enter fuel quantity (e.g., 15 liters)
6. **Admin**: Submit - Bill generated automatically
7. **User**: Login with Wallet ID
8. **User**: View bill in "My Bills"
9. **User**: Check updated wallet balance

## 📝 Sample Data

The system uses `datasets/valid_prepaid_wallet.csv` for wallet data.

Sample wallet entry:
```
number_plate_id,wallet_id,balance,last_recharge_amount,last_recharge_date,total_transactions,fuel_type,vehicle_type
DL3CAB1234,W1,500.0,500.0,2024-01-15,1,Petrol,Car
```

## ⚠️ Important Notes

1. **Camera Access**: Browser may ask for camera permission - allow it
2. **HTTPS Required**: For camera access, use HTTPS or localhost
3. **CSV Files**: Transactions and bills are stored in CSV files (auto-created)
4. **Demo Mode**: Email sending is placeholder - not actually sent

## 🐛 Troubleshooting

### Issue: Camera not working
- **Solution**: Use HTTPS or ensure you're on localhost
- Check browser permissions

### Issue: Wallet not found
- **Solution**: Verify vehicle plate format matches database
- Check CSV file exists and has correct format

### Issue: Module not found
- **Solution**: Ensure virtual environment is activated
- Run: `pip install -r requirements.txt`

## 📚 Next Steps

1. Review the full [README.md](README.md) for detailed documentation
2. Explore all admin and user features
3. Test the bill generation workflow
4. Check transaction history
5. Try wallet recharge

---

**Happy Testing!** 🎉


