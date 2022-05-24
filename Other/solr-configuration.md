# Configuring Solr on Lando

1. Go to the Search API page and create new solr server (skip it if you already have it)
2. On the Searh APi page your server appeared and from the Operations dropdown menu choose option Get config.zip
3. unzip the downloaded folder and all the files from it paste into the instance directory for your core eg. /var/solr/data/CORENAME (you can find this from the SOLR core dashboard page if you have one). Copy the elevate.xml file into the data directory which is usually the folder beneath where uoi copied the other config files above (again the data directory is viewable from the SOLR core dashboard page)
4. run lando restart (if using lando) and your solr server should work. You can check status of it on Search API page.
