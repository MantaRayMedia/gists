### Configuration needed for indexing attachments in ES7 and Solr

1. install via composer
![](../assets/indexing-attachment1.png)

2. configure _Search API Attachments_
```
download file https://archive.apache.org/dist/tika/tika-app-1.24.jar
```
![](../assets/indexing-attachment2.png)

3. enable Indexing of attachments for `resource`
![](../assets/indexing-attachment3.png)

4. define exclusions and adjust size if needed
![](../assets/indexing-attachment4.png)

5. add `attachments_field` to search api indexing
![](../assets/indexing-attachment5.png)

6. change `string` to `fulltext`
![](../assets/indexing-attachment6.png)
