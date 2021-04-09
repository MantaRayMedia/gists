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

### Load Taxonomy children for known parent
```
$vid = 'my_vocab_machine_name';
$parent_tid = 87;           // the parent term id
$depth = 1;                 // 1 to get only immediate children, NULL to load entire tree
$load_entities = FALSE;     // True will return loaded entities rather than ids
$child_tids = \Drupal::entityTypeManager()->getStorage('taxonomy_term')->loadTree($vid, $parent_tid, $depth, $load_entities);
$children = $this->entityTypeManager->getStorage('taxonomy_term')->loadChildren($object->tid);
```


### Extending the ContentEntityBase
Note that the entity has no properties. Those are all defined in baseFieldDefinitions and accessed through set/get with the property's name.

```php
use Drupal\Core\Entity\ContentEntityBase;
use Drupal\Core\Entity\EntityTypeInterface;
use Drupal\Core\Entity\EntityChangedTrait;
use Drupal\Core\Field\BaseFieldDefinition;


/**
 * @ingroup firebase_push_notification
 *
 * @ContentEntityType(
 *   id = "contact",
 *   label = @Translation("Contact entity"),
 *   handlers = {
 *     "view_builder" = "Drupal\Core\Entity\EntityViewBuilder",
 *     "views_data" = "Drupal\views\EntityViewsData",
 *   },
 *   base_table = "contact",
 *   admin_permission = "administer contact entity",
 *   fieldable = TRUE,
 *   entity_keys = {
 *     "id" = "id",
 *     "created_at" = "created_at", 
 *     "name" = "name",    
 *     "address" = "address",    
 *     "email" = "email"
 *   },
 * )
 */
class Contact extends ContentEntityBase {
  
  use EntityChangedTrait; // Implements methods defined by EntityChangedInterface.

  public function __construct($values = []) {
    
    parent::__construct($values, 'contact'); //this must be the same name as the id field in the annotations

    if(!isset($values['created_at'])) {
      $this->setCreatedAt((new DateTime())->getTimestamp());
    }
  }
  
  /**
   * @return string
   */
  public function getId(): int
  {
    return $this->get('id')->value;
  }

  /**
   * @param string $id
   * @return self
   */
  public function setId(int $id): Contact
  {
    $this->set('id', $id);
    return $this;
  }
  
  //getters and setters like above for every field...
  
  /**
   * @return Address
   */
  public function getAddress(): Address
  {
    return $this->get('address')->entity;
  }

  /**
   * @param int $addressId
   * @return self
   */
  public function setAddress(int $addressId): Contact
  {
    $this->set('address', $addressId);
    return $this;
  }
  
  /**
  * {@inheritdoc}
  *
  * Define the field properties here.
  *
  * Field name, type and size determine the table structure.
  *
  * In addition, we can define how the field and its content can be manipulated
  * in the GUI. The behaviour of the widgets used can be determined here.
  */
  public static function baseFieldDefinitions(EntityTypeInterface $entity_type)
  {

    // Standard field, used as unique if primary index.
    $fields['id'] = BaseFieldDefinition::create('integer')
      ->setLabel(t('ID'))
      ->setDescription(t('The ID of the FirebaseMessage entity.'))
      ->setReadOnly(true);

    $fields['created_at'] = BaseFieldDefinition::create('integer')
      ->setLabel(t('Created at'))
      ->setDescription(t('The time the contact was created at.'))
      ->setSettings(array(
        'default_value' => '',
        'max_length' => 255,
        'text_processing' => 0,
      ));

    $fields['name'] = BaseFieldDefinition::create('string')
      ->setLabel(t('Name'))
      ->setDescription(t('The name of the contact.'))
      ->setSettings(array(
        'default_value' => '',
        'max_length' => 255,
        'text_processing' => 0,
      ));

    $fields['email'] = BaseFieldDefinition::create('email')
      ->setLabel(t('Email'))
      ->setDescription(t('The contact\'s email.'))
      ->setSettings(array(
        'default_value' => '',
        'max_length' => 255,
        'text_processing' => 0,
      ));
      
    //assuming we have an entity somewhere with id 'address'
    $fields['address'] = BaseFieldDefinition::create('entity_reference')
      ->setLabel(t('Address'))
      ->setDescription(t('The contact\'s address.'))
      ->setSettings(array(
        'target_type' => 'address',
        'default_value' => '',
        'max_length' => 255,
        'text_processing' => 0,
      ));
      
    return $fields;
  }
}

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

Putting that into practice with above example of extending the `ContentEntityBase`.
```php
/** $result contains IDs */
$result = \Drupal::entityQuery('contact')
      ->condition('address', 1)
      ->sort('created', 'DESC')             // sort by date created
      ->range(0, 9)                         // show only results 0-9
      ->execute();
      
//instantiate the objects, turning the array of IDs into an array of Contacts
$contacts = \Drupal::entityTypeManager()->getStorage('contact')->loadMultiple($result);

```

### Deleting a single entity
```php
/** $result contains IDs */
$result = \Drupal::entityQuery('contact')
      ->condition('address', 1)
      ->sort('created', 'DESC')             // sort by date created
      ->range(0, 9)                         // show only results 0-9
      ->execute();
      
//instantiate the objects, turning the array of IDs into an array of Contacts
$contact = \Drupal::entityTypeManager()->getStorage('contact')->load(reset($result));
$contact->delete();
```

### Delete multiple entities
```
/** $result contains IDs */
$result = \Drupal::entityQuery('taxonomy_term')
      ->condition('vid', 'libraries') // vocabulary machine name
      ->execute();
entity_delete_multiple('taxonomy_term', $result);
```

OR

```php
$result = \Drupal::entityQuery('contact')
      ->condition('address', 1)
      ->sort('created', 'DESC')             // sort by date created
      ->range(0, 9)                         // show only results 0-9
      ->execute();
      
//instantiate the objects, turning the array of IDs into an array of Contacts
$contacts = \Drupal::entityTypeManager()->getStorage('contact')->loadMultiple($result);
\Drupal::entityTypeManager()->getStorage('contact')->delete($contacts);
```


### Adding a new field to a custom entity
```
$new_field = BaseFieldDefinition::create('string')
  ->setLabel(new TranslatableMarkup('New Field'))
  ->setDescription(new TranslatableMarkup('New field description.'));
\Drupal::entityDefinitionUpdateManager()->installFieldStorageDefinition('<field_name>', '<entity_type_id>', '<provider>', $new_field);
```

### Adding a new entity to an already installed plugin
```php
function firebase_push_notification_update_9102() {
  \Drupal::entityDefinitionUpdateManager()->installEntityType((new \Drupal\firebase_push_notification\Entity\Notification())->getEntityType());
}
```

Where 9 is the major Drupal version (could also be 7/8)
1 is the minor Drupal version
0 is the module's major version
2 is the module's minor version
`\Drupal\firebase_push_notification\Entity\Notification` is the newly created entity, extending ContentEntityBase

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
