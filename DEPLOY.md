# Deploy SkyBook AI to AWS EC2

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  AWS EC2 Instance (t3.small or t2.micro free tier)   │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐        │
│  │ Frontend │  │ Backend  │  │  PostgreSQL  │        │
│  │ (Next.js)│  │ (FastAPI)│  │  (Docker)    │        │
│  │ :3000    │→ │ :8000    │→ │  :5432       │        │
│  └──────────┘  └──────────┘  └──────────────┘        │
│                                                       │
│  All running via docker-compose                      │
└──────────────────────────────────────────────────────┘
         │
    Security Group
    (Inbound: 22, 80, 443, 3000, 8000)
```

## Prerequisites

1. **AWS account** — https://aws.amazon.com (free tier: 750 hrs/month t2.micro for 12 months)
2. **AWS CLI** installed on your Mac — `brew install awscli` then `aws configure`
3. Your `.env` file ready with all API keys (Twilio, Resend, Groq/Gemini)
4. A key pair `.pem` file for SSH access

---

## Step 1: Launch an EC2 Instance (AWS Console)

1. Go to **EC2 → Instances → Launch Instance** at https://console.aws.amazon.com/ec2

2. Fill in:
   - **Name**: `skybook-ai`
   - **AMI**: Ubuntu Server 22.04 LTS (free tier eligible)
   - **Instance type**: `t2.micro` (free tier) or `t3.small` (recommended — 2GB RAM)
   - **Key pair**: Create a new key pair → name it `skybook-key` → download `skybook-key.pem`
   - **Storage**: 20 GB gp2 (free tier allows 30 GB)

3. Under **Network settings → Edit**:
   - Allow **SSH** (port 22) from My IP
   - Add rule: Custom TCP, port **3000**, source `0.0.0.0/0`
   - Add rule: Custom TCP, port **8000**, source `0.0.0.0/0`
   - Add rule: HTTP port **80**, source `0.0.0.0/0`

4. Click **Launch Instance**.

> **Note:** `t2.micro` (1 GB RAM) may run out of memory with all three services running.  
> `t3.small` (2 GB RAM) at ~$17/month is much more stable.

---

## Step 2: Connect via SSH (from your Mac)

```bash
# Fix key permissions (required by SSH)
chmod 400 ~/Downloads/skybook-key.pem

# Get your EC2 public IP from the AWS Console → Instances → Public IPv4 address
# then SSH in:
ssh -i ~/Downloads/skybook-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

---

## Step 3: Install Docker on the EC2 Instance

Run these commands inside the EC2 SSH session:

```bash
# Update system packages
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add ubuntu user to docker group (no sudo needed for docker)
sudo usermod -aG docker ubuntu
newgrp docker

# Verify
docker --version
docker compose version
```

---

## Step 4: Upload Your Project to EC2

**Option A — From GitHub (recommended):**
```bash
# On EC2, clone your repo
git clone https://github.com/YOUR_USERNAME/airline-chatbot.git
cd airline-chatbot
```

**Option B — SCP from your Mac (if not on GitHub):**
```bash
# Run this on your Mac (not inside EC2)
scp -i ~/Downloads/skybook-key.pem -r \
  /Users/vigneshp/Documents/myPOc/airline-chatbot \
  ubuntu@YOUR_EC2_PUBLIC_IP:~/airline-chatbot
```

---

## Step 5: Create the .env File on EC2

```bash
# On EC2, inside the project folder
cd ~/airline-chatbot
nano .env
```

Paste your complete `.env` content:

```env
# LLM
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_API_KEY_SID=SKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_API_KEY_SECRET=your_api_key_secret
TWILIO_FROM_NUMBER=+17372508034
TWILIO_WHATSAPP_CONTENT_SID=HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_TRIAL_MODE=true

# Resend Email
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
RESEND_FROM_EMAIL=onboarding@resend.dev

# Security — generate a strong random string
SECRET_KEY=replace-with-a-long-random-secret-key

# PostgreSQL
POSTGRES_PASSWORD=choose-a-strong-db-password

# CORS — add your EC2 public IP
CORS_ORIGINS=http://YOUR_EC2_PUBLIC_IP:3000,http://localhost:3000
```

> **Important:** Do NOT add `DATABASE_URL` — docker-compose sets it automatically.

---

## Step 6: Update CORS for EC2 IP

The `docker-compose.yml` sets CORS to `localhost` by default. Override it:

```bash
# Edit docker-compose.yml and update the CORS_ORIGINS line for backend:
nano docker-compose.yml
```

Change:
```yaml
- CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```
To:
```yaml
- CORS_ORIGINS=http://YOUR_EC2_PUBLIC_IP:3000,http://localhost:3000,http://127.0.0.1:3000
```

---

## Step 7: Build and Start All Services

```bash
cd ~/airline-chatbot

# Build and launch (first time takes 3-5 minutes)
docker compose up -d --build

# Watch the logs while it starts up
docker compose logs -f

# Check all services are running
docker compose ps
```

Expected output:
```
NAME                          STATUS
airline-chatbot-postgres-1    Up (healthy)
airline-chatbot-backend-1     Up
airline-chatbot-frontend-1    Up
```

---

## Step 8: Access Your App

Replace `YOUR_EC2_PUBLIC_IP` with the IP from **EC2 Console → Instances → Public IPv4 address**:

| Service | URL |
|---|---|
| **Chat UI** | `http://YOUR_EC2_PUBLIC_IP:3000` |
| **Admin Panel** | `http://YOUR_EC2_PUBLIC_IP:3000/admin` |
| **Backend API** | `http://YOUR_EC2_PUBLIC_IP:8000` |
| **API Docs** | `http://YOUR_EC2_PUBLIC_IP:8000/api/docs` |
| **Health Check** | `http://YOUR_EC2_PUBLIC_IP:8000/api/health` |

Admin credentials: `admin@skybook.ai` / `admin123`

---

## Step 9: Add a Swap File (Required for t2.micro)

`t2.micro` has only 1 GB RAM. Add 2 GB swap to prevent OOM kills:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Persist across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
# Should show: Swap: 2.0G
```

---

## Step 10: Set Up Nginx as Reverse Proxy

Nginx sits on port 80 so users access the app without port numbers in the URL.  
It routes `/` → Next.js (3000) and `/api/` + `/ws/` → FastAPI (8000).

```bash
sudo apt-get install -y nginx
```

Create the site config:

```bash
sudo nano /etc/nginx/sites-available/skybook
```

Paste this:

```nginx
server {
    listen 80;
    server_name YOUR_EC2_PUBLIC_IP;   # replace with your IP or domain

    # Frontend — Next.js
    location / {
        proxy_pass         http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API — FastAPI
    location /api/ {
        proxy_pass         http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # WebSocket — chat
    location /ws/ {
        proxy_pass         http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_read_timeout 3600s;
    }
}
```

Enable and start:

```bash
# Disable default nginx site
sudo rm -f /etc/nginx/sites-enabled/default

# Enable skybook site
sudo ln -s /etc/nginx/sites-available/skybook /etc/nginx/sites-enabled/

# Test config — must say "test is successful"
sudo nginx -t

# Start/reload nginx
sudo systemctl enable nginx
sudo systemctl restart nginx
```

Your app is now accessible at **`http://YOUR_EC2_PUBLIC_IP`** (no port number).

> **Security Group:** Make sure port **80** is open in your EC2 Security Group inbound rules.

### Add HTTPS with Certbot (if you have a domain)

```bash
sudo apt-get install -y certbot python3-certbot-nginx

# Replace yourdomain.com with your actual domain
sudo certbot --nginx -d yourdomain.com

# Auto-renew (runs twice daily)
sudo systemctl enable certbot.timer
```

Update `nginx.conf` `server_name` to your domain, then Certbot handles the rest.

---

## Step 11: Set Up PM2 for Process Management

PM2 manages the docker compose process — auto-restarts on crash and survives EC2 reboots.

```bash
# Install Node.js (needed for PM2)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PM2 globally
sudo npm install -g pm2

# Verify
pm2 --version
```

Create a PM2 ecosystem config:

```bash
cd ~/airline-chatbot
nano ecosystem.config.js
```

Paste:

```js
module.exports = {
  apps: [
    {
      name: 'skybook-ai',
      script: 'docker',
      args: 'compose up',
      cwd: '/home/ubuntu/airline-chatbot',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_restarts: 10,
      restart_delay: 5000,
      env: {
        NODE_ENV: 'production',
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
};
```

Start with PM2:

```bash
# Stop any running docker compose first
docker compose down

# Start via PM2
pm2 start ecosystem.config.js

# Check it's running
pm2 status

# View logs
pm2 logs skybook-ai

# Save PM2 process list
pm2 save

# Enable PM2 auto-start on reboot
pm2 startup
# ↑ This prints a command — COPY and RUN that command, e.g.:
#   sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u ubuntu --hp /home/ubuntu
```

### PM2 Useful Commands

```bash
# Check status of all processes
pm2 status

# View live logs
pm2 logs skybook-ai --lines 50

# Restart
pm2 restart skybook-ai

# Stop
pm2 stop skybook-ai

# Delete from PM2
pm2 delete skybook-ai

# Monitor CPU/RAM
pm2 monit
```

---

## Final Architecture After Steps 9–11

```
Browser
   │  port 80 (http) or 443 (https)
   ▼
┌────────────────────────────────┐
│         Nginx (host)           │
│  / → localhost:3000            │
│  /api/ → localhost:8000        │
│  /ws/ → localhost:8000         │
└────────────────────────────────┘
         │               │
         ▼               ▼
  ┌──────────┐    ┌──────────────┐
  │ Frontend │    │   Backend    │
  │ Next.js  │    │   FastAPI    │
  │  :3000   │    │   :8000      │
  └──────────┘    └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │  PostgreSQL  │
                  │    :5432     │
                  └──────────────┘
         All managed by PM2 → docker compose
```

---

## Useful Commands

```bash
# Check service status
docker compose ps

# View real-time logs
docker compose logs -f backend
docker compose logs -f frontend

# Rebuild after code changes
docker compose up -d --build

# Restart a single service
docker compose restart backend

# Stop everything
docker compose down

# Full reset (deletes DB data)
docker compose down -v

# Connect to PostgreSQL directly
docker compose exec postgres psql -U skybook -d skybook

# Check memory / CPU usage
docker stats
free -h
```

---

## Cost Estimate

| Resource | Monthly Cost |
|---|---|
| t2.micro (free tier, 1 GB RAM) | **Free** for 12 months |
| t3.small (2 GB RAM, recommended) | ~$17/month |
| 20 GB gp2 storage (free tier) | **Free** for 30 GB / 12 months |
| Data transfer out | Free up to 100 GB/month |
| Elastic IP (if assigned) | Free while instance is running |
| **Total (free tier)** | **$0/month for 12 months** |

---

## Troubleshooting

### Backend can't connect to PostgreSQL
```bash
docker compose logs postgres
docker compose logs backend
# Wait for postgres to be healthy, then restart backend
docker compose restart backend
```

### CORS error in browser
```bash
# Ensure EC2 public IP is in CORS_ORIGINS in docker-compose.yml
docker compose down && docker compose up -d
```

### Out of memory (OOM killed)
```bash
free -h
# Add swap (see Step 9) or upgrade to t3.small
```

### Port not accessible from browser
- Check **EC2 Security Group** has inbound rules for ports 3000 and 8000
- EC2 Console → Security Groups → Edit Inbound Rules

### Connection refused after reboot
```bash
# Restart services
cd ~/airline-chatbot && docker compose up -d
# Or if you set up systemd service: sudo systemctl start skybook
```
