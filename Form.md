### Load form display for specific node
```
$node_storage = \Drupal::entityTypeManager()->getStorage('node');

// create empty content type, can also use existing node if have an ID of it (check in Entity.md for how to's...)
$newNode = $node_storage->create([
  'type' => 'resource',
]);
$form = \Drupal::service('entity.form_builder')->getForm($newNode, 'form_machine_name');  // can be: default, step_1,...
```
