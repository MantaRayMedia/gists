#!/bin/bash
#####################
# copy the file to server /usr/local/bin
# change permission to execute (sudo chmod +x)
# define php service name; get it from (sudo service --status-all)
# edit cronjobs (sudo crontab -e)
# add new entry to run every minute on the server(* * * * * /bin/bash /usr/local/bin/is-php-running.sh)
#####################

service=php53-fpm

if (( $(ps -ef | grep -v grep | grep $service | wc -l) == 0 ))
  then
    echo -e "`date` - php-fpm was not running, starting" >> /var/log/php-fpm-status.log
    /etc/init.d/$service start
  else
    echo -e "`date` - php-fpm OK" >> /var/log/php-fpm-status.log
fi