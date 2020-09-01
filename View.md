### Get render array for selected view
```
use Drupal\views\Views;
$args = [];
$view = Views::getView('my_view');
$view->setDisplay('my_display'); // the view name
$view->preExecute();
$view->execute();
$render_array = $view->buildRenderable('my_display', $args);

// Get rendered markup:
Drupal::service('renderer')->renderRoot($render_array);
```

### Get IDs and objects
```
// Get query object (must be called after `execute()`)
$query = $view->query;

// Get view ID
$view->id();

// Get current display
$view->current_display();

// Get results
$view->result;
```
