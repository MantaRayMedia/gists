<?php

use Drupal\Core\Database\Database;

$connection = Database::getConnection();

// Step 1: Map internal machine names to human-friendly headers in the order we want.
$layoutMap = [
  'layout_onecol' => 'One column',
  'layout_twocol_section' => 'Two column',
  'layout_twocol' => 'Two column burger',
  'layout_twocol_bricks' => 'Two column bricks',
  'layout_threecol_section' => 'Three column',
  'layout_threecol_25_50_25' => 'Three columns 25/50/25',
  'layout_threecol_33_34_33' => 'Three columns 33/34/33',
];

// Step 2: Get layout counts from behavior_settings in 'paragraphs_item_field_data' table only from
// 'field_postscript_nuggets' field.
$query = $connection->select('paragraphs_item_field_data', 'p')
  ->fields('p', ['behavior_settings'])
  ->condition('parent_field_name', 'field_postscript_nuggets');

$results = $query->execute();

$rawCounts = [];
foreach ($results as $row) {
  $settings = unserialize($row->behavior_settings);
  if (!empty($settings['layout_paragraphs']['layout'])) {
    $layout = $settings['layout_paragraphs']['layout'];
    $rawCounts[$layout] = ($rawCounts[$layout] ?? 0) + 1;
  }
}

// Step 3: Prepare final mapped output. Project name will manually be updated for each site
$project = 'PROJECT_NAME';
$csvHeaders = array_merge(['Project'], array_values($layoutMap));
$csvValues = [$project];

// Initialize all layout counts to 0.
foreach ($layoutMap as $machine_name => $label) {
  $csvValues[] = $rawCounts[$machine_name] ?? 0;
}

// Step 4: Output as CSV row.
echo implode(',', $csvHeaders) . "\n";
echo implode(',', $csvValues) . "\n";
