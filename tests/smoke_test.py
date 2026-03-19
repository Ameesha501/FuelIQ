import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.ocr import read_plate_text_from_image
from utils.yolo_detect import detect_plate_bbox
from utils.wallet import WalletManager
import numpy as np
import cv2

def safe_run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"EXC in {fn.__name__}:", repr(e))
        return None

img = np.full((240,320,3), 255, dtype=np.uint8)
cv2.rectangle(img, (50,80), (200,140), (0,0,0), -1)

print('Running OCR...')
print(safe_run(read_plate_text_from_image, img))

print('Running YOLO detect...')
print(safe_run(detect_plate_bbox, img))

print('Testing WalletManager...')
wm = safe_run(WalletManager, 'datasets/test_wallet.csv')
print('Loaded wallet:', type(wm))
print('Find existing plate:', safe_run(lambda: wm.find_by_plate('DL3CAB1234')))
print('Recharge new plate...')
print(safe_run(lambda: wm.recharge('NEWPLATE1', 150)))
print('Find new plate:', safe_run(lambda: wm.find_by_plate('NEWPLATE1')))
print('Debit existing plate...')
print(safe_run(lambda: wm.debit('DL3CAB1234', 10)))
print('Post-debit:', safe_run(lambda: wm.find_by_plate('DL3CAB1234')))
