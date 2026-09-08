# Huawei Cloud ECS deployment

## Cloud prerequisites

1. Create an ECS in a private VPC subnet and attach an EIP for outbound
   DashScope traffic.
2. In its security group, allow SSH only from an administrator IP and UDP
   51820 for WireGuard. Do not expose ports 80, 443, 5432, or 8000 publicly.
3. Create private OBS data and release buckets.
4. Create an ECS IAM agency with access to the selected OBS buckets and attach
   it to the ECS.
5. Clone this repository to `/opt/omni`.

## Configure and start

```bash
cd /opt/omni
cp deploy/.env.example deploy/.env
openssl rand -hex 32
openssl rand -hex 32
# Put the generated values and cloud configuration into deploy/.env.
chmod 600 deploy/.env
./deploy/install-ecs.sh
```

The API is bound to loopback and Nginx only allows `127.0.0.1` and the
WireGuard client subnet `10.8.0.0/24`.

## WireGuard

```bash
sudo install -m 0600 deploy/wireguard/wg0.conf.example /etc/wireguard/wg0.conf
# Replace all placeholders, then:
sudo systemctl enable --now wg-quick@wg0
sudo wg show
```

Import `deploy/wireguard/android.conf.example` into the Android WireGuard app
after replacing its placeholders. `AllowedIPs` deliberately uses only
`10.8.0.0/24` so Glass3 Wi-Fi P2P and normal Internet routes remain untouched.

## Android debug build

The enrollment token is lower privilege than the DashScope API key, but it must
still be managed outside Git:

```powershell
$env:OMNI_BACKEND_BASE_URL="http://10.8.0.1"
$env:OMNI_DEVICE_ENROLLMENT_TOKEN="<same value as backend>"
cd glass3sdkphonedemo
.\gradlew.bat assembleDebug
```

Only the debug manifest permits cleartext HTTP/WS inside the encrypted
WireGuard tunnel. Release builds require HTTPS/WSS.

## Operations

```bash
cd /opt/omni/deploy
sudo systemctl status omni
docker compose ps
docker compose logs --tail=200 api
sudo nginx -t
sudo wg show
curl http://127.0.0.1/health
```

To update:

```bash
cd /opt/omni
git pull --ff-only
sudo systemctl restart omni
```
