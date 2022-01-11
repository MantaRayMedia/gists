# Invalid characters
If you get this error `Your github oauth token for github.com contains invalid characters` run the following command, replacing `<github_username` with your github username and `<github_token>` with a github OAUTH token generated over here: https://github.com/settings/tokens

`lando composer config --global --auth http-basic.github.com "<github_username>" "<github_token>"`
