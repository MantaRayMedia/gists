### Load a user with ID 1
```
$user = \Drupal\user\Entity\User::load( 1 );
```

### Get current user
```
$user = \Drupal::currentUser();
```

### Get current user ID
```
$uid = \Drupal::currentUser()->id();
```

### Get user field value (*username*, *field_first_name*, *roles*,...)
```
$user = \Drupal\user\Entity\User::load( 1 );
$username =  $user->get('name')->value;
$roles = $user->getRoles();
```
