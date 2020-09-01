### Render array for an image style
```
$render = [
  '#theme' => 'image_style',
  '#style_name' => 'thumbnail',
  '#uri' => 'public://my-image.png',
];
```

### Image style, get URL (full URL including SCHEME -> http, https)
```
$style = \Drupal::entityTypeManager()->getStorage('image_style')->load('thumbnail');
$image_url = $style->buildUrl('public://image.jpg');
```

### Image style, get URI (public://path-to-image-style).
```
$style = ImageStyle::load('thumbnail');
$image_url = $style->buildUri('public://image.jpg');
```
