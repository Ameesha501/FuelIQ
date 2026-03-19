import requests

print("Testing endpoints...")
r = requests.get('http://127.0.0.1:5000/dashboard')
print(f"dashboard: {r.status_code}")

r = requests.get('http://127.0.0.1:5000/scan')
print(f"scan: {r.status_code}")

r = requests.post('http://127.0.0.1:5000/invoice', json={'plate':'TEST','liters':5,'rate':100,'fuel':'Petrol','total':500})
print(f"invoice: {r.status_code}")

print("All endpoints OK!" if all([r.status_code == 200]) else "Some endpoints failed")
