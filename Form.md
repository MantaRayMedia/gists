### Load form display for specific node
```
$node_storage = \Drupal::entityTypeManager()->getStorage('node');

// create empty content type, can also use existing node if have an ID of it (check in Entity.md for how to's...)
$newNode = $node_storage->create([
  'type' => 'resource',
]);
$form = \Drupal::service('entity.form_builder')->getForm($newNode, 'form_machine_name');  // can be: default, step_1,...
```

## Example of adding field to forum settings
### Add additional item to config
Adding 'forum_intro' field in you custom module .schema.yml file
```
forum.settings.third_party.custom_extensions:
  type: mapping
  label: 'Forum settings'
  mapping:
    topics:
      type: mapping
      label: 'Forum topics block'
      mapping:
        forum_intro:
          type: text
          label: 'Forum description'

```
### Alter form to add custom field
Adding a custom 'Forum introduction' field to forum settings page
```
function custom_extensions_form_alter(&$form, FormStateInterface $form_state, $form_id)
{
  if ($form["#id"] === 'forum-admin-settings') {
    $config = \Drupal::service('config.factory')->getEditable('forum.settings');
    $form['forum_intro'] = array(
      '#type' => 'textarea',
      '#title' => t('Forum introduction'),
      '#description' => t('Description text'),
      '#default_value' => $config->get('topics.forum_intro') ? $config->get('topics.forum_intro') : '',
      '#weight' => 1
    );
    $form['actions']['submit']['#submit'][] = 'custom_submit_handler';
  }
}
```

### Custom submit handler to save to form settings

```
function custom_submit_handler($form, FormStateInterface $form_state) {
  $config = \Drupal::service('config.factory')->getEditable('forum.settings')
    ->set('topics.hot_threshold', $form_state->getValue('forum_hot_topic'))
    ->set('topics.page_limit', $form_state->getValue('forum_per_page'))
    ->set('topics.order', $form_state->getValue('forum_order'))
    ->set('topics.forum_intro', $form_state->getValue('forum_intro'))
    ->save();
}
```