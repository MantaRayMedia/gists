### Render custom blocks
```
$bid = 'myblock';
$block = \Drupal\block_content\Entity\BlockContent::load($bid);
$render = \Drupal::entityTypeManager()->getViewBuilder('block_content')->view($block);
```

### Render plugin blocks
```
$block_manager = \Drupal::service('plugin.manager.block');
$config = [];
$plugin_block = $block_manager->createInstance('system_breadcrumb_block', $config);
$access_result = $plugin_block->access(\Drupal::currentUser());
if (is_object($access_result) && $access_result->isForbidden() || is_bool($access_result) && !$access_result) {
  return [];
}
$render = $plugin_block->build();
```
