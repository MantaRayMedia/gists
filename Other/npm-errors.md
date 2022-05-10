# Node / npm errors
Make sure the `node --version` is __v12.22.10__.

You can control local versions of Node with `nvm` > https://github.com/nvm-sh/nvm#installing-and-updating 

## Error `gyp ERR! stack     at ChildProcess.onExit`
```bash
npm --version`
```
If version is __7__ or __8__:
```bash
npm explore npm/node_modules/@npmcli/run-script -g -- npm_config_global=false npm install node-gyp@latest
```
If version is __less than 7__:
```bash
npm explore npm/node_modules/npm-lifecycle -g -- npm install node-gyp@latest
```

## Error `permodials`
- Delete `node_modules` and `package.lock` in the theme
- update `package.json` to look like this (... is other entries that stay there):
```json
{
  ...
  "devDependencies": {
    "gulp": "^3.9.1",
    "gulp-sass": "*",
    "node-sass": "^4.14.1",
    ...
  },
  "dependencies": {
    "sass": "^1.35.2"
  },
  "scripts": {
    "preinstall": "npx npm-force-resolutions",
    ...
  },
  "resolutions": {
    "graceful-fs": "^4.2.9"
  }
}
```
Then run
```bash
npm install --force
```
