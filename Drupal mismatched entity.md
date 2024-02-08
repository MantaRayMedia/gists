## Script that fixes `Mismatched entity` in update hook

```
function MT_MODULE_update_N(): string
{
  $entity_type_manager = \Drupal::entityTypeManager();
  $entity_type_manager->clearCachedDefinitions();

  $entity_type_ids = [];
  $change_summary = \Drupal::service('entity.definition_update_manager')->getChangeSummary();
  foreach ($change_summary as $entity_type_id => $change_list) {
    $entity_type = $entity_type_manager->getDefinition($entity_type_id);
    \Drupal::entityDefinitionUpdateManager()->installEntityType($entity_type);
    $entity_type_ids[] = $entity_type_id;
  }
  drupal_flush_all_caches();

  return t("Installed/Updated the entity type(s): @entity_type_ids", [
    '@entity_type_ids' => implode(', ', $entity_type_ids),
  ]);
}
```