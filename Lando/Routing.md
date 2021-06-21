# Lando
This document is meant for trouble shooting for Lando Routing

## Domains aren't working
If one or multiple custom URLs show up as red in the terminal like below, the easiest fix is to add the domain to the hosts file.
![image](https://user-images.githubusercontent.com/81559360/122742442-dae33380-d27d-11eb-94b9-a10a9abb0ebd.png)

### Linux / Mac
```
sudo vim /etc/hosts
127.0.0.1 <your domain>
127.0.0.1 tephinet-accreditation.lndo.site
```

### Windows
```
notepad c:\windows\system32\drivers\etc\hosts
127.0.0.1 <your domain>
127.0.0.1 tephinet-accreditation.lndo.site
```
