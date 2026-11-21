"""앱 스크립트가 가려서 보낸 sync/dump.bin 을 푼다 (키: 환경변수 SYNC_KEY).
형식: 첫 줄 nonce, 둘째 줄 base64(gzip(글자) XOR HMAC-SHA256(키, "nonce:번호") 키스트림)"""
import base64, gzip, hashlib, hmac, os, sys
src, out = sys.argv[1], sys.argv[2]
key = os.environ['SYNC_KEY'].encode()
nonce, b64 = open(src, encoding='ascii').read().split('\n', 1)
data = base64.b64decode(b64.strip())
buf = bytearray(len(data))
for c in range((len(data) + 31) // 32):
    ks = hmac.new(key, f'{nonce}:{c}'.encode(), hashlib.sha256).digest()
    for j in range(32):
        i = c * 32 + j
        if i >= len(data): break
        buf[i] = data[i] ^ ks[j]
open(out, 'w', encoding='utf-8').write(gzip.decompress(bytes(buf)).decode('utf-8'))
print('unsealed', len(data))
