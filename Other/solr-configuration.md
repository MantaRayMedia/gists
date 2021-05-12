# Configuring Solr server

1. Go to the Search API page and create new solr server (skip it if you already have it)
2. On the Searh APi page your server appeared and from the Operations dropdown menu choose option Get config.zip
3. unzip the downloaded folder and all the files from it paste into web/modules/contrib/search_api_solr/solr-conf/7.x
4. run lando restart and your solr server should work. You can check status of it on Search API page.
