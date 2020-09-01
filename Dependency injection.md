## Service

### services.yml:
```
services:
  custom_search.taxonomy_tree_builder:
    class: Drupal\custom_search\TaxonomyTreeBuilder
    arguments: [ '@entity_type.manager' ]
```

### Service file
```
  /**
   * TaxonomyTreeBuilder constructor.
   * @param EntityTypeManagerInterface $entityTypeManager
   */
  public function __construct(EntityTypeManagerInterface $entityTypeManager)
  {
    $this->entityTypeManager = $entityTypeManager;
  }
```

## Controller or Form

### Controller/Form File
```
  /**
   * {@inheritdoc}
   */
  public function __construct(TaxonomyTreeBuilder $tree_builder) {
    $this->treeBuilder = $tree_builder;
  }

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container) {
    return new static(
      $container->get('custom_search.taxonomy_tree_builder')
    );
  }
```
