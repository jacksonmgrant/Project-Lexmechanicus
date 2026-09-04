# Hosting RuleFinder at rulefinder.app

This guide deploys RuleFinder on one small Ubuntu VPS using Docker Compose and Caddy. It is intentionally uncomplicated: the app, PostgreSQL, Redis, MinIO, and HTTPS reverse proxy run together; only ports 80 and 443 are public. Caddy obtains and renews TLS certificates automatically.

## Recommended low-cost setup

Use a small Hetzner Cloud shared-vCPU instance (at least 2 vCPU and 4 GB RAM) in the region closest to your users. This is a sensible low-cost starting point because it provides a normal Linux server with SSH access, a firewall, and enough memory for the database, object storage, API, and frontend to coexist. Use a larger instance before expecting sustained traffic or large file-processing workloads.

The application uses its own Docker volumes for database and uploaded-file persistence, so there is no separate database or object-storage bill in this starter setup. Your ongoing costs are the VPS, the RuleFinder/OpenAI usage, and any backup storage you choose.

## Before you begin

You need:

- A Git repository that contains this project and is readable from the server.
- A Hetzner Cloud account, or another VPS provider with an Ubuntu 24.04 LTS server and public IPv4 address.
- `rulefinder.app` DNS control.
- An OpenAI API key and, if used, an OpenAI vector-store ID.

## 1. Create and secure the server

1. Create an Ubuntu 24.04 server with your SSH public key. Choose 2 vCPU / 4 GB RAM or larger.
2. In the provider firewall, allow inbound TCP ports `22`, `80`, and `443`. Do not expose PostgreSQL, Redis, MinIO, or the API port.
3. Connect as root and create a deployment user:

```bash
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy /root/.ssh /home/deploy
```

4. Reconnect as that user, then install Docker Engine and the Compose plugin using Docker's current Ubuntu instructions. Verify both commands work:

```bash
docker --version
docker compose version
```

5. Allow the deployment user to run Docker without `sudo`, then sign out and back in:

```bash
sudo usermod -aG docker deploy
```

## 2. Point rulefinder.app at the server

At the DNS provider for `rulefinder.app`, create these records, replacing the sample address with the VPS IPv4 address:

| Type | Host | Value |
| --- | --- | --- |
| A | `@` | `203.0.113.10` |
| A | `www` | `203.0.113.10` |

Wait for both names to resolve before starting the web container. Caddy needs the DNS records and public ports 80/443 to issue HTTPS certificates.

## 3. Clone and configure RuleFinder

Run the following as `deploy`:

```bash
mkdir -p ~/apps
cd ~/apps
git clone <YOUR-REPOSITORY-SSH-URL> Project-Lexmechanicus
cd Project-Lexmechanicus
cp .env.production.example .env
chmod 600 .env
```

Edit `.env` and replace every `replace-with-...` value. Generate strong secrets locally or on the server, for example:

```bash
openssl rand -base64 48
```

The `POSTGRES_PASSWORD` embedded in `DATABASE_URL` must exactly match `POSTGRES_PASSWORD`. Leave `PUBLIC_APP_URL`, `CORS_ORIGINS`, and `DOMAIN` set to `rulefinder.app` unless you deliberately use another domain. Do not commit `.env`.

## 4. Start the production stack

```bash
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
curl --fail https://rulefinder.app/health
```

On its first start, the API applies its Alembic migrations. RuleFinder creates its MinIO bucket when the first upload is made. Caddy serves the compiled frontend and forwards the API routes internally; the browser uses same-origin requests, so no public API URL is required.

If certificate provisioning fails, first verify DNS and the firewall. Inspect logs with:

```bash
docker compose -f docker-compose.production.yml logs --tail=100 web
```

## Updating the app

Every future release is one SSH session and one command:

```bash
ssh deploy@YOUR_SERVER_IP
cd ~/apps/Project-Lexmechanicus
./scripts/deploy-production.sh
```

The script performs a fast-forward `git pull`, rebuilds changed images, recreates affected containers, and leaves Docker volumes intact. It intentionally refuses a non-fast-forward pull, which prevents accidental deployment over uncommitted server changes.

To inspect an update:

```bash
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs --tail=100 api web
```

## Backups and recovery

The production data lives in named Docker volumes. Take backups before upgrades that change data or before modifying production configuration.

Create a database backup:

```bash
docker compose -f docker-compose.production.yml exec -T db pg_dump -U rulefinder rulefinder > rulefinder-$(date +%F).sql
```

Copy that file off the server. Also back up the `minio_data` Docker volume, which contains uploaded files. A simple low-cost approach is a daily encrypted copy of database dumps and MinIO data to a separate storage provider. Test a restore before relying on any backup plan.

## Operating notes

- Never run `docker compose down -v` in production: the `-v` removes the database and uploaded-file volumes.
- Keep Ubuntu security updates current and restrict SSH to key authentication.
- OpenAI and file-processing costs can exceed VPS cost; set account alerts and review usage regularly.
- This is a single-server deployment. For high availability, managed backups, or significant traffic, move PostgreSQL and object storage to managed services and run multiple application instances.
