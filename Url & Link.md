### current URL path
```
current_path = \Drupal::service('path.current')->getPath();
$pathArr = explode('/', $current_path);

// will return from http://icrc-wathab.lndo.site/resource/add/step2/41265573-af22-4046-b0c9-ee43fbfffd58
array(
    0 => 'icrc-wathab.lndo.site',
    1 => 'resource',
    2 => 'add',
    3 => 'step2',
    4 => '41265573-af22-4046-b0c9-ee43fbfffd58',
)
```

### URL from route
```
use Drupal\Core\Url;
$url = Url::fromRoute($route_name, $params, $options);
```

### URL from URI
```
use Drupal\Core\Url;
$url = Url::fromUri('internal:/path/to/style.css');
```

### Add options to an existing URL (classes, target, etc)
```
$url->setOptions([
  'attributes' => [
    'target' => '_blank',
  ],
]);
```

### Generate a link
```
$my_link = \Drupal::service('link_generator')->generate($text, Url $url);

// OR

use Drupal\Core\Link;
$renderable_link = Link::fromTextAndUrl($text, Url $url);
```

### Create a link from route
```
Link::createFromRoute($text, $route_name, ['arg1' => 'value'], ['attributes' => ['class' => 'use-ajax']]);
```

### Convert generated link to rendered array or link string.
```
$link_render_array = $renderable_link->toRenderable();

$link_string = $renderable_link->toString();
```
