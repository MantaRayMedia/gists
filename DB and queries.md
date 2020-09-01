## DB and queries

### Simple database query
```
$results = \Drupal::database()->query('select * from my_table')->fetchAll();
```

### Debugging an entity query, enable the devel module and add tag before execute.
```
$entity_query->addTag('debug')->execute();
```

### entityQuery: range query with BETWEEN
```
$result = \Drupal::entityQuery('node')
  ->condition('field_number', [1, 3], 'BETWEEN')
  ->execute();
```

### entityQuery: IS NULL (and IS NOT NULL)
```
$result = \Drupal::entityQuery('node')
  ->condition('field_banner_code', NULL, 'IS NULL')
  ->execute();
```

### entityQuery: Delete all nodes of type 'event'
```
$result = \Drupal::entityQuery('node')
  ->condition('type', 'event')
  ->execute();
entity_delete_multiple('node', $result);
// Add ->range(0, 10) to delete a range
```

### Insert statement
```
$query = \Drupal::database()->insert('my_table');
$query->fields([
  'uid' => $this->user->id(),
  'custom_field' => 'MRM',
  'created' => 371304000
]);
$query->execute();
```

### Update statement
```
$query = \Drupal::database()->update('my_table');
$query->fields(['custom_field' => 'MRM new']);
$query->condition('uid', $this->user->id());
$query->execute();
```

### Delete statement
```
$query = \Drupal::database()->delete('my_table');
$query->condition('created', 1577836800, '<');
$query->execute();
```
