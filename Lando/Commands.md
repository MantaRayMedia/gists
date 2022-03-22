# Lando commands
Some commands to help manage your local Lando environment

# Changing settings for local
Updates the SMTP host and port so emails won't go out when copying the dev DB
Updates all user passwords to the defined password or cheese if unspecified

```bash
# Usage: localise-drupal [user-password]
function localise-drupal() {
    lando drush config:set "smtp.settings" "smtp_host" "mailhog" -y
    lando drush config:set "smtp.settings" "smtp_port" "1025" -y
    lando drush config:set "smtp.settings" "smtp_username" " " -y
    lando drush config:set "smtp.settings" "smtp_password" " " -y

    set-users-pass $1
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
# Usage: set-users-pass [user-password]
function set-users-pass() {
    local PASS=$1

    # default to cheese if no password is provided
    if [ -z $PASS ]; then
       PASS='cheese'
    ;fi

    lando drush sql:query "SELECT name FROM users_field_data WHERE name != ''" | while read name; do
        if [ ! -z "$name" ]; then
          echo "$(echo $name | tr -d '\r'): $PASS \r"
          lando drush user:pass "$(echo $name | tr -d '\r')" "$PASS" --quiet < /dev/null 2>&1 > /dev/null
          echo "\r"
        ;fi
    done
}

```
