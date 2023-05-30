# Lando commands
Some commands to help manage your local Lando environment

# Update lando
## Ubuntu
Command will automatically grab the latest version of lando and installs it.

```
lando-update () {
        lando poweroff
        sudo systemctl stop docker
        local TEMP_DEB="$(mktemp)" 
        wget -O "$TEMP_DEB" "https://files.lando.dev/installer/lando-x64-stable.deb"
        sudo dpkg -i "$TEMP_DEB"
        sudo systemctl start docker
}
```

# Changing settings for local
Updates the SMTP host and port so emails won't go out when copying the dev DB  
Updates all user passwords to the defined password or cheese if unspecified  
This command depends on [Updating all users' password](https://github.com/MantaRayMedia/gists/blob/master/Lando/Commands.md#updating-all-users-password)

```bash
# Make the drupal config safe for local development
# Updates the solr config
# Updates the smtp config
# Changes all user passwords to the one provided, or cheese if none provided
#
# Requires localise-solr and localise-mail
#
# Usage: localise-drupal [user-password]
function localise-drupal() {
    localise-solr 
    localise-mail
    set-users-pass $1
}
```

## Localising solr

```bash
# Make the solr config safe for local development and indexes all items
#
# Usage localise-solr
localise-solr () {
	if [ $(lando drush pm:list --type=module --status=enabled --no-core --fields=name | grep "search_api" | wc -l) -ne 0 ]
	then
		echo "SOLR installed"
		SEARCH_API_SERVER=$(lando drush search-api:server-list | grep -i "solr" | awk '{print $1;}') 
		SEARCH_API_CORE=$(lando info --format=json | jq '.[].core' | grep -v "null" | tr -d '"') 
		SEARCH_API_CONFIG_KEY="search_api.server.$SEARCH_API_SERVER" 
		SEARCH_API_BASE_KEY="backend_config.connector_config" 
		lando drush config:set $SEARCH_API_CONFIG_KEY "$SEARCH_API_BASE_KEY.host" "search" -y
		lando drush config:set $SEARCH_API_CONFIG_KEY "$SEARCH_API_BASE_KEY.core" $SEARCH_API_CORE -y
		lando drush config:set $SEARCH_API_CONFIG_KEY "$SEARCH_API_BASE_KEY.path" "/" -y
		lando drush search-api:reset-tracker
		lando drush search-api:index
	fi
}
```

## Localising mail

```bash
# Make the mail config safe for local development and sends a test email
#
# Usage localise-solr
localise-mail () {
	lando drush config:set "smtp.settings" "smtp_on" "true" -y
	lando drush config:set "smtp.settings" "smtp_host" "mailhog" -y
	lando drush config:set "smtp.settings" "smtp_port" "1025" -y
	lando drush config:set "smtp.settings" "smtp_protocol" "standard" -y
	lando drush config:delete "smtp.settings" "smtp_username" -y
	lando drush config:delete "smtp.settings" "smtp_password" -y
	lando drush php:eval "mail('support@mantaraymedia.co.uk', 'Localised email settings', 'Hello mailhog :)', 'From: support@mantaraymedia.co.uk');"
	echo "Sent test email"
}
```

# Reinstalling a module
```bash
# Usage: module-reinstall <module_name>
function module-reinstall() {
  lando drush pmu $1 
  lando drush pm:enable $1
}
```

# Updating all users' password
```bash
# Updates all users their password to the one provided, or cheese if none provided
# Usage: set-users-pass [user-password]
function set-users-pass() {
    local PASS=$1

    # default to cheese if no password is provided
    if [ -z $PASS ]; then
       PASS='cheese'
    ;fi

    lando drush sql:query "SELECT name FROM users_field_data WHERE name != ''" | while read name; do
        if [ ! -z "$(echo $name | tr -d '\r')" ]; then
          echo "$(echo $name | tr -d '\r'): $PASS \r\n"
          lando drush user:pass "$(echo $name | tr -d '\r')" "$PASS" --quiet < /dev/null &> /dev/null
        ;fi
    done
}

```

# DB Import 
```bash
# Import database and update smtp, mailhog and user passwords
# Usage: db-import <database>
function db-import() {
  lando db-import $1
  lando drush cr 
  localise-drupal
  lando drush cr
}
```

# Local update
```bash
# Runs composer install, cim and update-db
function lu() {
  lando composer install
  lando drush cr
  lando drush cim -y
  lando drush cr
  lando drush updatedb -y
  lando drush cr
  lando ant
}
```
