### Load a file
```
$file = \Drupal\file\Entity\File::load(1007);

// OR

$file = \Drupal::entityTypeManager()->getStorage('file')->load(1007);
```

### Working with file entities
```
// Get the URI (including wrapper, such as public://)
$uri = $file->getFileUri();

// Get the full URL path
$url = file_create_url($file->getFileUri());

// Get relative path of the URL (w/o domain)
$path = file_url_transform_relative($url);
```
