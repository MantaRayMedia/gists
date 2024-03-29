## Miscellaneous
### Get the node from the current path
```
$node = \Drupal::routeMatch()->getParameter('node');
```

### Get current path and it's arguments
```
$path = \Drupal::service('path.current')->getPath();
$path_args = explode('/', $path);
```

### Get the current route
```
$route_name = \Drupal::service('current_route_match')->getRouteName();
```

### Save file to public path
```
$output = 'Some file contents';
$realBasePath = \Drupal::service('file_system')->realpath("public://");
$filesystem = new Filesystem();
$filesystem->dumpFile(sprintf('%s/%s', $realBasePath, $fileName), $output);
```

### Redirect
```
use Symfony\Component\HttpFoundation\RedirectResponse;
new RedirectResponse(\Drupal::url($route_name));
```

### Statistics (total count of node view)
```
$statistics = \Drupal::service('statistics.storage.node')->fetchView($variables['node']->id());
$total_count = \Drupal::translation()->formatPlural( $statistics->getTotalCount(), '1 view', '@count views' );
```

### When module not there anymore and get errors on `cim`
```
drush sql:query "DELETE FROM key_value WHERE collection='system.schema' AND name='PROBLEMATIC_MODULE';"
```

### Twig keeps throwing OutOfMemoryExceptions when doing a dump (local only)
```
https://stackoverflow.com/questions/14913859/twigs-dump-function-returns-a-blank-screen
```
