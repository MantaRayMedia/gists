# Setting up a new Remora8 the easy way

1. Add the following code to your `~/.bashrc`
```
export REMORA_COMPOSER_REPOSITORIES="remora_custom_extensions remora_ui_module rem8min remora_base_theme remora_config twitter_feed entity_reference_media_enhanced drush9_custom_commands"
export REMORA_LIBRARIES="jquery-ui-touch-punch.zip"

function new-remora() {
  if [ -z $1 ]; then
    echo "Please specify a directory to clone into"
    return
  ;fi

  if [ -z $2 ]; then
    echo "Please specify a project name"
    return
  ;fi

  echo "Cloning remora into $1"

  git clone git@github.com:MantaRayMedia/Remora8.git $1
  cd $1

  echo "Copying config"
  cp -r config/for_blank_project/. .
  sed -i "s/RANDOM_PORT/$RANDOM/g" .lando.yml
  sed -i "s/PROJECT_NAME_IN_LOWERCASE/$(echo $2 | tr '[:upper:]' '[:lower:]'|tr -s ' '|tr ' ' '_')/g" .lando.yml


  lando start

  echo -e "\033[0;31mPlease install the \e[4mMinimal\e[0m\033[0;31m site\033[0m"
  echo "Don't forget to change db host from localhost to database. All credentials are drupal9"
  echo "Waiting for user input..."
  read -n 1

  echo "Updating hash_salt"
  grep "\$settings\['hash_salt'\] = '" web/sites/default/default.settings.php >> config/settings.local.php

  echo "Adding repositories to composer.json"
  IFS=' '; for module in "$REMORA_COMPOSER_REPOSITORIES"; do
    lando composer config "repositories.mantaraymedia/$module" vcs "git@github.com:MantaRayMedia/$module.git"
    lando composer require $module "^1.0"
  done

  lando drush pm:e drush9_custom_commands remora_config
  lando drush rte -y
  lando drush cex -y
  lando drush rci -y
  lando drush cex -y

  for lib in "$REMORA_LIBRARIES"; do
    echo "installig $lib";
    lando drush rli --library "$lib"
  done


  lando drush rci -y
  lando drush cex -y

  cd web/themes/contrib
  IFS=$'\n'; for f in $(find "$(pwd)" -maxdepth 1 ! -path "$(pwd)" -type d); do cd $f && lando npm install && lando gulp; done

  echo "Have fun and don't forget to set config ignore"
  echo "Also setup Jenkins here: https://www.notion.so/mantaray/Prepare-project-for-Jenkins-AWS-c7dc23ec6b6043c6ad81b2abdd6ef99f"

}

```

2. Run `new-remora <directory> <project name>`

# Setting up Remora8 the hard way
https://github.com/MantaRayMedia/Remora8#create-new-site
