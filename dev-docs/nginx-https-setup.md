# Nginx HTTPS Reverse Proxy for DeoVR

## Why HTTPS is Required

DeoVR (and most modern VR apps) require HTTPS to load thumbnails and video URLs. A plain HTTP server returns thumbnail URLs starting with `http://`, which DeoVR blocks as mixed content.

With this setup:
- Nginx handles HTTPS/TLS termination using your Let's Encrypt certificate
- Nginx forwards requests to the Python server on `localhost:8000`
- Nginx injects `X-Forwarded-Proto: https` so the Python server generates correct `https://` URLs in DeoVR JSON

## Nginx Site Configuration

See: `nginx/arcade-scanner.conf` in this repo.

## Setup Steps

### 1. Copy config to Nginx

```bash
sudo cp /path/to/arcade-video-scanner/nginx/arcade-scanner.conf \
        /etc/nginx/sites-available/arcade-scanner
sudo ln -s /etc/nginx/sites-available/arcade-scanner \
           /etc/nginx/sites-enabled/arcade-scanner
```

### 2. Edit the config

Replace `YOUR_DOMAIN.com` with your actual domain (the one Let's Encrypt issued the cert for).

### 3. Verify and reload Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Enable DeoVR in Arcade Scanner settings

In the Settings panel of the app, enable **DeoVR** mode. This tells the app to serve the `/deovr` endpoint.

### 5. Point DeoVR at your domain

In DeoVR on your headset, go to **Settings → Library → Add** and enter:

```
https://YOUR_DOMAIN.com/deovr
```

DeoVR will discover your library including thumbnails, all served over HTTPS.
