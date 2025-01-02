`www/includes/common.inc:8904`

Remove
```
if (!empty($info['entity keys']['bundle'])) {
```

Replace with

```
// Sometimes an entity type is passed that does not match the actual entity, i.e. A paragraph $entity is passed, but $entity_type contains node
// This code checks if the entity is an object, has the entityInfo method and if so, checks if the bundle that is collected from entity_get_info matches the entityInfo bundle
// If it does, ignore this code and let the vendor code handle the bundle code
// If it does not, assume that the entity knows better
if(is_object($entity) && method_exists($entity, 'entityInfo')) {
  $myInfo = $entity->entityInfo();
  if(isset($myInfo['entity keys']['bundle']) && $entity->{$myInfo['entity keys']['bundle']} !== $entity->{$info['entity keys']['bundle']}) {
    $bundle = $entity->{$myInfo['entity keys']['bundle']};
  }
}
```

Example [here](https://github.com/MantaRayMedia/alnap/pull/111/files)
