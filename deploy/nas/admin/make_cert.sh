#!/bin/sh
# Makes the housekeeping website's self-signed HTTPS certificate on the NAS, once.  Run as pi:
#     sh /home/pi/Judicom/deploy/nas/admin/make_cert.sh
# The private key stays in /home/pi/judicom/tls, readable by pi only.  It is never put in the repository.
# Each browser warns once, because nobody vouches for this certificate.  What it is for is keeping the password off the network.
set -eu
dir=/home/pi/judicom/tls
if [ -f "$dir/cert.pem" ] && [ -f "$dir/key.pem" ]; then
    echo "There is a certificate already: $dir/cert.pem.  Nothing done."
    exit 0
fi
umask 077
mkdir -p "$dir"
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout "$dir/key.pem" -out "$dir/cert.pem" -subj "/CN=naspi.local" \
    -addext "subjectAltName=DNS:naspi.local,DNS:naspi,DNS:naspi-1,DNS:localhost" 2>/dev/null
chmod 600 "$dir/key.pem"
chmod 644 "$dir/cert.pem"
echo "Made $dir/cert.pem.  Restart the website:  sudo systemctl restart judicom-admin"
