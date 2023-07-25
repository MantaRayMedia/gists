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

# Adding custom fields
Create a new module. Then implement the following hook:
```php
function hook_views_data_alter(array &$data): void
{
  $data['node']['tephinet_access_groups'] = array(
    'title' => t('Webform access groups'),
    'group' => t('Content'),
    'field' => array(
      'title' => t('Webform access groups'),
      'help' => t('Displays the access groups for the webform on Calls.'),
      'id' => 'tephinet_access_groups',
    ),
  );
}
```

Add the ViewField which MUST match the `['field']['id']` above!

```php
namespace Drupal\custom_module\Plugin\views\field;

use Drupal\views\Plugin\views\field\FieldPluginBase;
use Drupal\views\ResultRow;

/**
 * @ViewsField("tephinet_access_groups")
 */
class AccessGroupsForm extends FieldPluginBase
{
  /**
   * @{inheritdoc}
   */
  public function query() {
    // Leave empty to avoid a query on this field.
  }

  /**
   * Called per row as the row is being rendered
   */
  public function render(ResultRow $values): array|string {
    $node = $this->getEntity($values);
    
    if($node->bundle() === 'my_bundle') {
      return 'Oh hi mark'; // plain text
    } else if($node->bundle() === 'my_other_ct') {
      return '<b>Oh hi mark!<b>'; // will return the literal text (not bold)
    }
    
    return ['#markup' => '<b>Oh hi mark!!!!!!!</b>']; // will return bold text 
  }
}
```
