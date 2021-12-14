# Scripts :)
generate `.version` file to be publicly accessible for every repo in the list

### Required files
- `.git-key` contains repo access key (ie ghp_GvUL0cpCW6z2ypxxxx)
- `repo-versions.sh` main file for generation
- `.git-repo-list` contains repository names to generate version file for
- `repo-consumer.sh` main file called by `crontab` that consumes the list above

### Files
generated files can bea accessed on MRM website: `https://www.mantaraymedia.co.uk/sites/default/files/rem8min.version`
