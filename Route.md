https://www.drupal.org/docs/8/api/routing-system

### Example route
```
example.name:
  path: '/example/{name}'
  defaults:
    _controller: '\Drupal\example\Controller\ExampleController::content'
    name: 'My name'
  requirements:
    _permission: 'access content'
```

### Using roles instead of permissions
Using a `,` among multiple roles means the user has to have all roles. Using a `+` means they need to have one.
```
requirements:
  _role: admin,accountant
```

### Allowing all access
```
requirements:
  _access: TRUE
```
