### Get parameter from header
```
$referer = \Drupal::request()->headers->get('referer');
```

### Parameter bag ($_GET and $_POST values)
```
// GET
$bag = \Drupal::request()->query;

// POST
$bag = \Drupal::request()->request;

// Get all parameters as array
$bag->all();

// Get individual parameter
$bag->get('name');

```

### Get the host (just in case don't know what a host is :P -> www.mantaraymedia.co.uk).
```
$host = \Drupal::request()->getHost();
```

### Get current request URI which on AJAX is different from URI
```
$current_uri = \Drupal::request()->getRequestUri();
```
