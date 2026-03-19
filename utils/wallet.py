# utils/wallet.py
import pandas as pd
import os, datetime, threading

class WalletManager:
    def __init__(self, csv_path="datasets/valid_prepaid_wallet_dataset.csv"):
        self.csv_path = csv_path
        self.lock = threading.Lock()
        self.df = None
        self._load()

    def _load(self):
        """Load wallet data from CSV file"""
        try:
            if not os.path.exists(self.csv_path):
                print(f"Warning: Wallet file {self.csv_path} not found. Creating sample file.")
                self.create_sample(self.csv_path)
            
            # Read CSV with proper error handling
            self.df = pd.read_csv(self.csv_path, dtype=str, encoding='utf-8')
            
            # Ensure required columns exist
            required_columns = ['number_plate_id', 'wallet_id', 'balance']
            missing_columns = [col for col in required_columns if col not in self.df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Normalize identifiers to avoid lookup mismatches caused by spacing/case
            self.df['number_plate_id'] = (
                self.df['number_plate_id']
                .astype(str)
                .str.upper()
                .str.replace(r"\s+", "", regex=True)
                .str.strip()
            )
            self.df['wallet_id'] = (
                self.df['wallet_id']
                .astype(str)
                .str.upper()
                .str.replace(r"\s+", "", regex=True)
                .str.strip()
            )

            # Convert balance to numeric
            if 'balance' in self.df.columns:
                self.df['balance'] = pd.to_numeric(self.df['balance'], errors='coerce').fillna(0.0)
            else:
                self.df['balance'] = 0.0
            
            # Ensure other numeric columns are properly converted
            if 'total_transactions' in self.df.columns:
                self.df['total_transactions'] = pd.to_numeric(self.df['total_transactions'], errors='coerce').fillna(0).astype(int)
            
            if 'last_recharge_amount' in self.df.columns:
                self.df['last_recharge_amount'] = pd.to_numeric(self.df['last_recharge_amount'], errors='coerce').fillna(0.0)
            
            print(f"Loaded {len(self.df)} wallet records from {self.csv_path}")
        except Exception as e:
            print(f"Error loading wallet file: {e}")
            # Create sample file as fallback
            self.create_sample(self.csv_path)
            self.df = pd.read_csv(self.csv_path, dtype=str)
            if 'balance' in self.df.columns:
                self.df['balance'] = pd.to_numeric(self.df['balance'], errors='coerce').fillna(0.0)
            else:
                self.df['balance'] = 0.0

    def reload(self, new_csv_path):
        self.csv_path = new_csv_path
        self._load()

    def create_sample(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        sample = pd.DataFrame([{
            "number_plate_id":"DL3CAB1234",
            "wallet_id":"W1",
            "balance":500.0,
            "last_recharge_amount":500.0,
            "last_recharge_date": str(datetime.date.today()),
            "total_transactions":1,
            "fuel_type":"Petrol",
            "vehicle_type":"Car"
        }])
        sample.to_csv(path, index=False)

    def find_by_plate(self, plate_text):
        if not plate_text:
            return None
        df = self.df
        row = df[df['number_plate_id'].astype(str).str.upper() == plate_text.upper()]
        if row.empty:
            return None
        r = row.iloc[0].to_dict()
        r['balance'] = float(r.get('balance',0.0))
        return r

    def find_by_wallet_id(self, wallet_id):
        """Find wallet record by wallet_id"""
        if not wallet_id:
            return None
        df = self.df
        row = df[df['wallet_id'].astype(str).str.upper() == wallet_id.upper()]
        if row.empty:
            return None
        r = row.iloc[0].to_dict()
        r['balance'] = float(r.get('balance',0.0))
        return r

    def _write(self):
        """Write wallet data to CSV file with error handling"""
        with self.lock:
            try:
                # Create backup before writing
                if os.path.exists(self.csv_path):
                    backup_path = self.csv_path + '.backup'
                    try:
                        import shutil
                        shutil.copy2(self.csv_path, backup_path)
                    except Exception:
                        pass
                
                # Write to CSV
                self.df.to_csv(self.csv_path, index=False, encoding='utf-8')
            except Exception as e:
                print(f"Error writing wallet file: {e}")
                raise

    def debit(self, number_plate_id, amount, note=None):
        """Debit amount from wallet"""
        if not number_plate_id:
            raise ValueError("Number plate ID is required")
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        with self.lock:
            idx = self.df[self.df['number_plate_id'].astype(str).str.upper() == number_plate_id.upper()].index
            if len(idx) == 0:
                raise ValueError(f"Plate not found: {number_plate_id}")
            
            i = idx[0]
            # Get current balance
            current_balance = float(self.df.loc[i, 'balance'])
            
            # Check if sufficient balance
            if current_balance < float(amount):
                raise ValueError(f"Insufficient balance. Current: ₹{current_balance:.2f}, Required: ₹{float(amount):.2f}")
            
            # Update balance
            self.df.loc[i, 'balance'] = current_balance - float(amount)
            
            # Update total transactions
            try:
                cur = int(self.df.loc[i].get('total_transactions', 0))
            except (ValueError, TypeError):
                cur = 0
            self.df.loc[i, 'total_transactions'] = cur + 1
            
            self._write()
            return float(self.df.loc[i, 'balance'])  # Return new balance

    def recharge(self, number_plate_id, amount):
        """Recharge wallet with amount"""
        if not number_plate_id:
            raise ValueError("Number plate ID is required")
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        with self.lock:
            idx = self.df[self.df['number_plate_id'].astype(str).str.upper() == number_plate_id.upper()].index
            if len(idx) == 0:
                # Create new wallet entry
                # Generate unique wallet ID
                existing_wallet_ids = set(self.df['wallet_id'].astype(str).str.upper())
                new_wallet_id = f"WALLET{len(self.df) + 1:06d}"
                counter = 1
                while new_wallet_id.upper() in existing_wallet_ids:
                    new_wallet_id = f"WALLET{len(self.df) + 1 + counter:06d}"
                    counter += 1
                
                new = {
                    'number_plate_id': number_plate_id.upper(),
                    'wallet_id': new_wallet_id,
                    'balance': float(amount),
                    'last_recharge_amount': float(amount),
                    'last_recharge_date': str(datetime.date.today()),
                    'total_transactions': 0,
                    'fuel_type': 'Petrol',  # Default
                    'vehicle_type': 'Car'    # Default
                }
                # Ensure all columns exist
                for col in self.df.columns:
                    if col not in new:
                        new[col] = ''
                
                # Add new row
                new_df = pd.DataFrame([new])
                self.df = pd.concat([self.df, new_df], ignore_index=True, sort=False)
            else:
                i = idx[0]
                current_balance = float(self.df.loc[i, 'balance'])
                self.df.loc[i, 'balance'] = current_balance + float(amount)
                self.df.loc[i, 'last_recharge_amount'] = float(amount)
                self.df.loc[i, 'last_recharge_date'] = str(datetime.date.today())
            
            self._write()
            # Return updated balance
            updated_idx = self.df[self.df['number_plate_id'].astype(str).str.upper() == number_plate_id.upper()].index[0]
            return float(self.df.loc[updated_idx, 'balance'])
