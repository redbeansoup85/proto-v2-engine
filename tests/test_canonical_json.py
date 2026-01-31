import hashlib
from core.canonical_json import canonical_json

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def test_canonical_vector_001():
    payload = {"observation_kind":"signal","metrics":[{"key":"score","value":"0.91"},{"key":"motion","value":True}]}
    c = canonical_json(payload)
    assert c.decode("utf-8") == '{"metrics":[{"key":"score","value":"0.91"},{"key":"motion","value":true}],"observation_kind":"signal"}'
    assert sha256_hex(c) == "44af65e9a4e19a1d98511190373ccec316a0b578f9c8fe79bb2007fbf343b7c0"

def test_canonical_vector_002():
    payload = {"inputs":{"source_ids":["snap-991.json","snap-992.json"]},"tags":["high","urgent"]}
    c = canonical_json(payload)
    assert c.decode("utf-8") == '{"inputs":{"source_ids":["snap-991.json","snap-992.json"]},"tags":["high","urgent"]}'
    assert sha256_hex(c) == "337f5bae0d6dcf95ddb00429e051f0404049c82ede3a0da751d0d8096fec32ed"

def test_canonical_vector_003():
    payload = {"value":42,"ratio":"0.333333","flag":None,"extra":{}}
    c = canonical_json(payload)
    assert c.decode("utf-8") == '{"extra":{},"flag":null,"ratio":"0.333333","value":42}'
    assert sha256_hex(c) == "75e279432b698c8a42412278365741966431a91178b30b46e871b06ee0bd7c1e"
