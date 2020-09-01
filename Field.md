### Basics

$node->field_example will return a `FieldItemList` object (or another class that extends `FieldItemList`)

If you add `->first()` you are targeting specific position. This is true if the field is a single item or multi-values.
Example: `$node->field_example->target_id` or `$node->field_example->first()->target_id`.

If the field is an entity reference, you can get the full entity: `$node->field_example->entity` (this gets the first entity if it's a multi-value).

On multi-value fields you can use the array index to target position: `$node->field_example[1]`.

### Entity reference
```
// Both of these return the same Entity ID value
$node->field_ref->target_id;
$node->field_ref->first()->target_id;

// Get the full entity. "->entity" is only valid when the field is an entity reference. Else throws a PHP error
$node->field_ref->entity;

// Get the value as an array: ['target_id' => '1']
$node->field_ref->getValue();

// Will return null
$node->field_ref->value;
```

### URL
```
$node->field_url->uri;
$node->field_url->title;
$node->field_url->options;    // Array of options
$node->field_url->entity;     // Returns null because it isn't an entity
$node->field_url->getValue(); // Returns ['uri' => '', 'title' => '', 'options => []]
$node->field_url->value;      // Returns null
```

### Text values
```
// Get the value as a string
$node->field_text->value;

// Get the value as an array: ['value' => 'text']
$node->field_text->getValue();
```
