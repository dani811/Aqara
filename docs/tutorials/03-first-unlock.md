# 03 — First autonomous unlock

> Precondition: `.env` filled (tutorial 02), a BLE transport available, and the
> lock awake (tap the keypad) and rested.

The full sequence — login, KDF, the auth handshake **with the CRC fix**,
verify, and the AES-CCM control write — is orchestrated by
`run_authenticated_lock_operation`.

```python
from aqara_u200_ble import make_local_signer, run_authenticated_lock_operation
import os

signer = make_local_signer(
    appid=os.environ["AQARA_APPID"],
    appkey=os.environ["AQARA_APPKEY"],
    token=os.environ["AQARA_TOKEN"],
    user_id=os.environ["AQARA_USER_ID"],
    client_id=os.environ["AQARA_CLIENT_ID"],
    phone_id=os.environ["AQARA_PHONE_ID"],
)
# ... connect your transport (see tools/), then:
# await run_authenticated_lock_operation(
#     bleak_client=adapter, device_id=os.environ["AQARA_DEVICE_ID"],
#     region=os.environ["AQARA_REGION"], operation="keepalive", signer=signer,
# )
```

Start with `operation="keepalive"` — it runs the full handshake without
actuating the bolt, so you confirm the wall is passed (the lock returns its
pubkey) before ever moving the lock. Then move to `"unlock"`.

> This is the integration tracked by
> [spec 005](../../specs/005-end-to-end-unlock/spec.md), with a fuller runnable
> walkthrough in [end-to-end-unlock.md](end-to-end-unlock.md). The hard blocker
> (the handshake) is solved and confirmed live; a clean end-to-end pass wants a
> rested lock.
