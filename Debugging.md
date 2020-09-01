## Debugging
### Display all errors
```
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);
```

### Display error messages (on the screen)
Set this in settings.local.php so that it displays locally, but not on prod. The default Logging and errors should be 'None'.

```
// none - display none
// some - errors and warning
// all - all messages
// verbose - all messages with backtrace information
$config['system.logging']['error_level'] = 'all';
```

### Set kint debug max level
If kint is taking forever to load or crashing the page (empty white screen), try reducing the max level.
```
// Change kint maxLevels setting.
include_once(DRUPAL_ROOT . '/modules/contrib/devel/kint/kint/Kint.class.php');
if(class_exists('Kint')){
  Kint::$maxLevels = 5;
}
```

### Services.yml debugging
You will need to copy `sites/example.settings.local.php` to `sites/default/settings.local.php` (and ensure settings.php includes settings.local.php) or put this in your settings.php file: `$settings['container_yamls'][] = DRUPAL_ROOT . '/sites/development.services.yml';`.

Update `/sites/development.services.yml`:
```
parameters:
  http.respone.debug_cacheability_headers: true
  twig.config:
    debug: true
    auto_reload: true
    cache: false
```

### Pretty print arrays/objects printed to watchdog
```
\Drupal::logger('my_module')->debug(kpr($var, TRUE));
```

### Debug backtrace any error
```
// This function exists in core/includes/bootstrap.inc.
// Just need to add lines 6-8 to it.
function _drupal_error_handler($error_level, $message, $filename, $line, $context) {
  require_once DRUPAL_ROOT . '/includes/errors.inc';
  require_once DRUPAL_ROOT . '/modules/contrib/devel/kint/kint.module';
  $d = debug_backtrace(DEBUG_BACKTRACE_IGNORE_ARGS);
  ksm($message, $d);
  _drupal_error_handler_real($error_level, $message, $filename, $line, $context);
}
```

### Debugging search API solr queries
```
// You can output the Request object using kint/kpm, but it can be hard
// to figure out where to set the debugging code. The best place is in
// the executeRequest function in the following file:
// search_api_solr/src/SolrConnector/SolrConnectorPluginBase.php
```

### Starting point for debugging ElasticSearch
```
// src/ElasticSearch/Parameters/Builder/SearchBuilder.php:

// Smaller oututs can be done via:
print '<PRE>'.print_r($var_name, true).'</PRE>';

// Add ksm at the end of build() and getSearchQueryOptions()
```
