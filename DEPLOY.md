# Deploying the CTF on a server (Linux or Windows)

> **Keep the GitHub repository PRIVATE.** It contains `flag.txt` for every challenge, the tutorial
> game's answers and the challenge solutions. A public repo would hand players every flag.

## 1. Push from your PC (once)

```bash
cd ctf                                   # the folder that contains pyproject.toml
git init -b main
git update-index --add --chmod=+x run.sh setup.sh   # keeps the scripts executable on Linux
git add .
git status                               # check: no .venv, lobby.json, *.bak, *.log in the list
git commit -m "GDG Universiapolis CTF"
```

Create an **empty private** repository on github.com (do not tick "add a README"), then:

```bash
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

(Shortcut with the GitHub CLI: `gh repo create gdg-ctf --private --source=. --push`)

Quick safety check - this must print nothing:
`git ls-files | grep -E "lobby.json|\.bak|\.venv|\.log|\.env"`

## 2. Linux server (Ubuntu/Debian)

```bash
sudo apt update && sudo apt install -y git python3 python3-venv
git clone https://github.com/<your-user>/<your-repo>.git && cd <your-repo>
./setup.sh                        # creates .venv and installs everything
cd demo && ../.venv/bin/ctf lint && cd ..     # optional: make sure the content is clean
tmux new -s ctf                   # keeps it running after you close the SSH window
./run.sh                          # prints the ADMIN TOKEN, starts the server (+ tunnel if installed)
```

Detach tmux with `Ctrl+B` then `D`; come back with `tmux attach -t ctf`.

*Private repo on the server:* run `gh auth login`, or create a **personal access token** (read-only,
"Contents: read") and use it as the password when git asks, or add an SSH **deploy key** to the repo.

**Letting players in** (pick one):

* **Cloudflare Tunnel (easiest, HTTPS, no open ports):** install `cloudflared`
  (<https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/>),
  then `./run.sh` prints a `https://....trycloudflare.com` link.
* **Direct on the server's IP:** `HOST=0.0.0.0 PORT=8000 ./run.sh`, open the port
  (`sudo ufw allow 8000/tcp` plus your cloud provider's firewall) and share `http://<server-ip>:8000`.

## 3. Windows server

1. Install **Git for Windows** and **Python 3.10+** (tick *Add python.exe to PATH*).
2. In PowerShell:
   ```powershell
   git clone https://github.com/<your-user>/<your-repo>.git
   cd <your-repo>
   .\setup.bat
   winget install cloudflare.cloudflared      # optional, for the public link
   .\run.bat
   ```
3. The admin token appears in the **ctf-server** window. Open `http://localhost:8000/admin`.
4. For direct access (no tunnel), open the firewall (admin PowerShell):
   `New-NetFirewallRule -DisplayName "CTF 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow`
   and start with `set HOST=0.0.0.0` first.

## 4. Event day checklist

1. `ctf lint` shows 0 errors (run inside `demo/`).
2. Start with `run.sh` / `run.bat` - every start **wipes scores and the lobby** (old scores are saved as
   `event.json.bak.*`). After a crash use `KEEP_STATE=1` to keep them.
3. Open `/admin`, paste the token, wait for the players, press **Start game**.
4. Put `/board` on the projector.

## 5. Updating the server later

```bash
git checkout -- demo/event.json     # drop the live scores/state first, otherwise git pull may complain
git pull
```

Never edit challenges on the server during an event; edit on your PC, push, then pull.
