### Load an entity
```
$node = \Drupal::entityTypeManager()->getStorage('node')->load(23);
$search_api_index = \Drupal::entityTypeManager()->getStorage('search_api')->load('title_records');
```

### Load multiple entities (if no param is passed, will return all records)
```
$node = \Drupal::entityTypeManager()->getStorage('node')->loadMultiple($entity_ids);
```

### Load Taxonomy and it's children
```
// let's say $object is the taxonomy term
$children = $this->entityTypeManager->getStorage('taxonomy_term')->loadChildren($object->tid);
```

### Custom query
```
/** $result contains IDs */
$result = \Drupal::entityQuery('node')
      ->condition('status', 1)              // is published
      ->condition('type', 'resource')       // sepcific content type
      ->sort('created', 'DESC')             // sort by date created
      ->range(0, 9)                         // show only specific number of results
      ->execute();
```

### Delete multiple entities
```
/** $result contains IDs */
$result = \Drupal::entityQuery('taxonomy_term')
      ->condition('vid', 'libraries') // vocabulary machine name
      ->execute();
entity_delete_multiple('taxonomy_term', $result);
```

### Adding a new field to a custom entity
```
$new_field = BaseFieldDefinition::create('string')
  ->setLabel(new TranslatableMarkup('New Field'))
  ->setDescription(new TranslatableMarkup('New field description.'));
\Drupal::entityDefinitionUpdateManager()->installFieldStorageDefinition('<field_name>', '<entity_type_id>', '<provider>', $new_field);
```

### Apply all entities changes
```
\Drupal::entityDefinitionUpdateManager()->applyUpdates();
```

### Checking for existence of fields on entities
```
Code | Field not empty | Field empty | Not a field
:--- | :--- | :--- | :---
!empty($node->field_entity_ref) | TRUE | TRUE | FALSE
!empty($node->field_entity_ref->first()) | TRUE | FALSE | PHP Error
!empty($node->field_entity_ref->first()->entity) | TRUE | FALSE | PHP Error
```
