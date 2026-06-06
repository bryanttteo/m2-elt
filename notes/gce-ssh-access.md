# Compute Engine access: SSH keys, not passwords

When you SSH into a GCP Compute Engine VM and get a **password prompt**, that is almost always
the **passphrase on your local SSH key** — *not* a VM/server login password.

## The key distinction
| | SSH key passphrase | VM account password |
|---|---|---|
| Lives on | **your laptop** (protects the private key) | the VM |
| Set by | **you**, when `gcloud compute ssh` first generated the key | n/a |
| Exists by default? | yes (if you typed one at key creation) | **no** — Linux GCP VMs are key-only |
| What it unlocks | your private key, *before* connecting | — |

So the prompt right after `gcloud compute ssh` unlocks your **local** key
(`~/.ssh/google_compute_engine`). The VM never sees it.

## How VM access actually works
- **Linux VMs** → **SSH-key based, no login password.** Connect via:
  - `gcloud compute ssh <vm> --zone <zone>` (gcloud auto-creates/uploads the key)
  - Console → VM → **SSH** button (browser, ephemeral key)
  - **OS Login** (IAM-based, recommended for teams)
  Password SSH is disabled by default (security best practice).
- **Windows VMs** → this is the only case with a real **user/password box**: Console
  **"Set Windows password"** (or `gcloud compute reset-windows-password`) generates RDP credentials.

## Practical tips (Linux)
```bash
# Forgot the passphrase? Regenerate the key (gcloud re-uploads the new public key):
rm ~/.ssh/google_compute_engine ~/.ssh/google_compute_engine.pub
gcloud compute ssh <vm> --zone <zone>      # set a new passphrase, or leave blank

# Tired of typing it? Cache it for the session:
ssh-add ~/.ssh/google_compute_engine

# Want no prompt at all? Press Enter (empty passphrase) at key creation.
# Less secure (anyone with the key file can use it) but fine for a dev box.
```

## Takeaway
A password prompt during `gcloud compute ssh` = **unlock my local SSH key**, set by you.
It is **not** a "computer password" GCP issued. Linux VMs have no default login password;
only Windows VMs hand you generated user/password credentials.
