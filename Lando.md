### to work with civiCrm locally
- change `$env` to 'dev' in sites/default/civicrm.settings.php and make sure all variables have 'dev' option
- add to `.lando.yml`
    ```
      civicrm_db:
        type: mysql
        creds:
          user: civicrm7
          password: civicrm7
          database: civicrm7
        portforward: RANDOM_PORT
    ```

### Lando elasticsearch not starting
```
lando stop

# check the size
lando ssh search -u root -c 'sysctl vm.max_map_count'

# if less than 262144, then update (usually run before lando start):
lando ssh search -u root -c 'sysctl -w vm.max_map_count=262144'

lando start

# if still issues then update on machine (not container)
sudo sysctl -w vm.max_map_count=262144
```

### Database conflicted encoding
```
# command to convert utf8mb4_0900_ai_ci to utf8mb4_unicode_ci encoding :

# MAC
sed -i '' 's/utf8mb4_0900_ai_ci/utf8mb4_unicode_ci/g' your_unzipped-sqlfile.sql

# Linux
sed -i 's/utf8mb4_0900_ai_ci/utf8mb4_unicode_ci/g' your_unzipped-sqlfile.sql

# Windows
do it manually :)
```

### MRM repositories complaining:
if you get an error `Your github oauth token for github.com contains invalid characters`:
1. lando ssh appserver
2. rm /var/www/.composer/auth.json
3. exit
4. try again
