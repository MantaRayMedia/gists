# AWS help

### Debug CodeDeploy
- login to box you are deploying to (there are 2 production boxes)
- run `tail -f /opt/codedeploy-agent/deployment-root/deployment-logs/codedeploy-agent-deployments.log`
- you will see the output of `hook` script
