alias drupal-9-to-10="update-9-to-10"
function update-9-to-10() {
  echo "Step 1" && lando drush en ckeditor5
  echo "Step 2 & 3: Go to /admin/config/content/formats. Press enter when done:" && read -n 1
  echo "Step 4" && lando drush pmu ckeditor
  echo "Step 5" && lando drush pmu rdf
  echo "Step 6" && lando composer require 'drupal/rdf:^2.1'
  echo "Step 7" && lando drush en rdf
  echo "Step 8" && lando drush pmu color
  echo "Step 9" && lando composer require 'drupal/color:^1'
  echo "Step 10" && lando drush en color
  echo "Step 11" && lando drush cex -y
  echo "Step 12" && lando composer require mglaman/composer-drupal-lenient
  echo "Step 13" && lando composer update slejnej/asset-installer
  echo "Step 14: Add the extra entries to composer.json" && read -n 1
  echo "Step 15: Update all modules/custom/*.info.yml files" && read -n 1
  echo "Step 16 & 18" && rm -Rf bin/ vendor/ web/modules/contrib web/themes/contrib web/core composer.lock
  echo "Step 17: Update drupal/core in composer.json to ^10" && read -n 1
  echo "Step 19: Remove the modules from composer.json" && read -n 1
  echo "Step 20" && lando composer update
  echo "Step 21: Fix all issues above. Only continue once you can successfully run lando composer update!" && read -n 1
  echo "Step 22-24" && lando composer require drupal/broken_link drupal/countries_info "drupal/stage_file_proxy:^2"

  echo "Step 25: Install mantaraymedia/remora_addon_countries_and_maps? [y/N]:"
  read -r response
  if [[ "$response" =~ ^(y|yes|Y)$ ]]
  then
    lando composer require mantaraymedia/remora_addon_countries_and_maps
  fi

  echo "Step 26" && lando composer require mantaraymedia/remora_config
  echo "Step 27" && lando drush updb -y
  echo "Step 28" && lando drush cr
  echo "Step 29" && lando drush updb -y

  echo "Don't forget to complete steps 30 and 31 :)"
}
