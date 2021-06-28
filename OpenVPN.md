## OpenVPN on AWS
- `cd ~/certificates`
- `source vars && ./build-key NAME`
- confirm all except email
- enter password
- then twice `y`
- `sudo cp /etc/openvpn/client/blank.ovpn /etc/openvpn/client/NAME.ovpn`
- `sudo vim /etc/openvpn/client/NAME.ovpn`
- `cat ~/certificates/keys/NAME.crt` and paste CERTIFICATE part into `<cert></cert>`
- `cat ~/certificates/keys/NAME.key` and paste into `<key></key>`
