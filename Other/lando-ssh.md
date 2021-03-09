# SSh on Lando

1. remove `lndo.site.*` from `/.lando/certs` folder
2. run `docker rm -f landoproxyhyperion5000gandalfedition_proxy_1`
3. import cert as defined per OS:

    ### macOS
    ```
    # Add the Lando CA
    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.lando/certs/lndo.site.pem
    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.lando/certs/lndo.site.crt
    
    # Remove Lando CA
    sudo security delete-certificate -c "Lando Local CA"
    ```
    
    ### Windows
    ```
    # Add the Lando CA
    certutil -addstore -f "ROOT" C:\Users\ME\.lando\certs\lndo.site.pem
    certutil -addstore -f "ROOT" C:\Users\ME\.lando\certs\lndo.site.crt
    
    # Remove Lando CA
    certutil -delstore "ROOT" serial-number-hex
    ```
    
    ### Debian / Ubuntu
    ```
    # Add the Lando CA
    sudo cp -r ~/.lando/certs/lndo.site.pem /usr/local/share/ca-certificates/lndo.site.pem
    sudo cp -r ~/.lando/certs/lndo.site.crt /usr/local/share/ca-certificates/lndo.site.crt
    sudo update-ca-certificates
    
    # Remove Lando CA
    sudo rm -f /usr/local/share/ca-certificates/lndo.site.pem
    sudo rm -f /usr/local/share/ca-certificates/lndo.site.crt
    sudo update-ca-certificates --fresh
    ```

4. next run `lando rebuild -y` and with boxes also the NEW certificate will be generated
5. import certificate as per browser:
    
    ### Firefox
    - go to `about:preferences#privacy` > `View Certificates` > `Authorities` > `Import`
    - import `~/.lando/certs/lndo.site.pem`
    - enable _Trust this CA to identify websites._
    
    ### Chrome
    - go to `chrome://settings/certificates`
    - if not in certificates section: `Privacy and Security` > `Security` > `Manage certificates` > `Authorities` > `Import`
    - import `~/.lando/certs/lndo.site.pem`
    - enable _Trust this CA to identify websites._

