<?php

/**
 * Update script to enable the option to scan for broken links for specific fields
 * Run this script and export your config to get all the field changes
 */
function MODULE_NAME_update_8001()
{

  // Fields to have linkchecker setttings updated
  $fieldList = [
    'field_1',
    'field_2',
    'etc',
  ];

  /** Change to `\Drupal\paragraphs\Entity\ParagraphsType::loadMultiple();` if loading paragraphs **/
  $types = \Drupal\node\Entity\NodeType::loadMultiple();

  // Create list of all content/paragraph types
  $types_list = [];
  foreach ($types as $machine_name => $type) {
    $types_list[] = $machine_name;
  }

  // Loop through all content/paragraph types and get the field definitions
  foreach ($types_list as $type) {
    /** Change the 'node' type to 'paragraph if updating paragraph fields **/
    $field_definitions = \Drupal::service('entity_field.manager')->getFieldDefinitions('node', $type);
    // Loop through all given fields updating the linkchecker settings
    foreach ($fieldList as $field) {
      if (isset($field_definitions[$field])) {
        $current_settings = $field_definitions[$field]->get('third_party_settings');
        $current_settings['linkchecker']['scan'] = true;
        $current_settings['linkchecker']['extractor'] = 'html_link_extractor';
        $field_definitions[$field]->set('third_party_settings', $current_settings);
        $field_definitions[$field]->save();
      }
    }
  }
}