## D7 modules via DB

### See all the modules that have been installed enabled or not
```
SELECT name,status FROM system WHERE type='module';
```

### See all the modules enabled
```
SELECT name,status FROM system WHERE type='module' AND status='1';
```

### See if a particular module is enabled
```
SELECT name,status FROM system WHERE name='module_name';
```

### Disable your module, set the status to 0 for the module name that you want to disable
```
UPDATE system SET status='0' WHERE name='module_name';
```

### Enable your module
```
UPDATE system SET status='1' WHERE name='module_name';
```
