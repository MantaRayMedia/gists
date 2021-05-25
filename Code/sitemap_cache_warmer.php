<?php
function sitemap_cache_warmer_menu() {
    $items['admin/sitemap_cache_warmer'] = array(
        'title' => 'Cache Warmer',
        'description' => 'sitemap_cache_warmer',
        'page callback' => 'sitemap_cache_warmer_crawlurl',
        'access arguments' => array('access administration pages'),
    );
    return $items;
}

function sitemap_cache_warmer_crawlurl() {
	global $base_url;
	shell_exec('nohup wget -q --user="mrm" --password="mrmdev" '.$base_url.'/sitemap.xml -O - | egrep -o "'.$base_url.'[^<]+" | wget -q -i - -O /dev/null --wait 1');
	drupal_set_message(t('Cache warmer is complete'),'status');
	drupal_goto('admin/content');
}
